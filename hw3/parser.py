
"""LL(1) recursive-descent parser for Funny.

Panic-mode recovery:
  - Recovers inside blocks at semicolons, closing braces, and
    likely statement starts.
  - Recovers at top level at semicolons, closing braces, and
    declaration starts.
  - Collects multiple syntax errors in one parse.
  - Returns a partial AST when syntax errors occur.
  - Includes token positions in diagnostics.
  - Guards against infinite recovery loops.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from lexer import Token, tokenize, LexerError
from ast_nodes import (
    Module, Function, Formula, VarDef, TypeInt, TypeBool, TypeArray, Position,
    Assign, If, While, Block, Assert, Assume,
    IntLit, BoolLit, Var, ArrayAccess, BinOp, UnOp, FunctionCall,
    Comparison, LogicalOp, Not, Quantifier,
    Expr, Condition, Statement,
)


class ParseError(Exception):
    def __init__(
        self,
        message: str,
        token: Optional[Token] = None,
    ):
        self.message = message
        self.token = token

        if token is not None:
            super().__init__(
                f"{message} at {token.line}:{token.column} "
                f"(got {token.type} {token.value!r})"
            )
        else:
            super().__init__(message)

    @property
    def line(self) -> Optional[int]:
        return self.token.line if self.token else None

    @property
    def column(self) -> Optional[int]:
        return self.token.column if self.token else None


DECL_START = {"FUNCTION", "IDENT"}

STATEMENT_START = {
    "LBRACE",
    "IF",
    "WHILE",
    "ASSERT",
    "ASSUME",
    "IDENT",
}


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.errors: List[ParseError] = []

    @staticmethod
    def _position(token: Token) -> Position:
        return Position(token.line, token.column, token.offset)

    # ---------- helpers ----------

    def _peek(self, k: int = 0) -> Optional[Token]:
        i = self.pos + k
        if 0 <= i < len(self.tokens):
            return self.tokens[i]
        return None

    def _at_end(self) -> bool:
        return self.pos >= len(self.tokens)

    def _check(self, *types: str) -> bool:
        token = self._peek()
        return token is not None and token.type in types

    def _match(self, *types: str) -> Optional[Token]:
        if self._check(*types):
            return self._advance()
        return None

    def _advance(self) -> Token:
        if self._at_end():
            raise ParseError("unexpected end of input")

        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def _expect(self, *types: str) -> Token:
        token = self._peek()

        if token is None:
            raise ParseError(
                f"unexpected end of input, expected one of {types}"
            )

        if token.type not in types:
            raise ParseError(
                f"expected one of {types}, got {token.type}",
                token,
            )

        return self._advance()

    # ---------- panic-mode recovery ----------

    def _synchronize(self, in_block: bool = False) -> None:
        """Skip malformed input to a safe synchronization point.

        Inside a block:
          - consume SEMICOLON;
          - leave RBRACE for parse_block();
          - stop before a likely next statement.

        At top level:
          - consume SEMICOLON or RBRACE;
          - stop before a likely next declaration.
        """
        start_pos = self.pos

        while not self._at_end():
            token = self._peek()

            if token is None:
                return

            if token.type == "RBRACE":
                if not in_block:
                    self._advance()
                return

            if token.type == "SEMICOLON":
                self._advance()
                return

            if in_block and token.type in STATEMENT_START:
                # Leave a potential next statement for the parser.
                return

            if not in_block and token.type in DECL_START:
                # Do not consume a new declaration.
                # If recovery started at this token, return too:
                # the outer loop will retry parsing it.
                return

            self._advance()

        # EOF is also a valid stopping point for recovery.

    def _ensure_progress(
        self,
        previous_pos: int,
        in_block: bool = False,
    ) -> None:
        """Prevent recovery loops without discarding valid starts."""
        if self.pos != previous_pos or self._at_end():
            return

        token = self._peek()
        if token is None:
            return

        # These tokens are possible starts of the next construct.
        # Let the regular parser handle them instead of discarding them.
        if in_block and token.type in STATEMENT_START:
            return

        if not in_block and token.type in DECL_START:
            return

        # Otherwise consume one token to guarantee progress.
        self._advance()

    # ---------- top-level declarations ----------

    def parse(self) -> Tuple[Module, List[ParseError]]:
        functions: List[Function] = []
        formulas: List[Formula] = []

        while not self._at_end():
            start_pos = self.pos

            try:
                if self._check("FUNCTION"):
                    functions.append(self.parse_function())
                elif self._check("IDENT"):
                    formulas.append(self.parse_formula())
                else:
                    raise ParseError(
                        "expected function or formula declaration",
                        self._peek(),
                    )

            except ParseError as error:
                self.errors.append(error)
                self._synchronize(in_block=False)

            self._ensure_progress(start_pos, in_block=False)

        return Module(
            functions=functions,
            formulas=formulas,
        ), self.errors

    # ---------- functions and formulas ----------

    def parse_function(self) -> Function:
        self._expect("FUNCTION")
        name_token = self._expect("IDENT")

        self._expect("LPAREN")
        params = self.parse_params()
        self._expect("RPAREN")

        requires = None
        if self._match("REQUIRES"):
            requires = self.parse_predicate()

        self._expect("RETURNS")
        returns = self.parse_params()

        ensures = None
        if self._match("ENSURES"):
            ensures = self.parse_predicate()

        uses: List[VarDef] = []
        if self._match("USES"):
            uses = self.parse_local_vars()

        body = self.parse_statement()

        return Function(
            position=self._position(name_token),
            name=name_token.value,
            params=params,
            returns=returns,
            requires=requires,
            ensures=ensures,
            uses=uses,
            body=body,
        )

    def parse_formula(self) -> Formula:
        name_token = self._expect("IDENT")

        self._expect("LPAREN")
        params = self.parse_params()
        self._expect("RPAREN")

        self._expect("IMPLIES")
        body = self.parse_predicate()
        self._expect("SEMICOLON")

        return Formula(
            position=self._position(name_token),
            name=name_token.value,
            params=params,
            body=body,
        )

    # ---------- parameters and types ----------

    def parse_params(self) -> List[VarDef]:
        if self._check("RPAREN"):
            return []

        params = [self.parse_param()]

        while self._match("COMMA"):
            params.append(self.parse_param())

        return params

    def parse_param(self) -> VarDef:
        name = self._expect("IDENT")
        self._expect("COLON")
        typ = self.parse_type()

        return VarDef(
            position=self._position(name),
            name=name.value,
            type=typ,
        )

    def parse_type(self):
        token = self._expect("INT_TYPE", "BOOL_TYPE")
        if token.type == "BOOL_TYPE":
            return TypeBool(position=self._position(token))
        if self._match("LBRACKET"):
            self._expect("RBRACKET")
            return TypeArray(position=self._position(token))
        return TypeInt(position=self._position(token))

    def parse_local_vars(self) -> List[VarDef]:
        variables = [self.parse_local_var()]

        while self._match("COMMA"):
            variables.append(self.parse_local_var())

        return variables

    def parse_local_var(self) -> VarDef:
        name = self._expect("IDENT")
        typ = None

        if self._match("COLON"):
            typ = self.parse_type()

        return VarDef(
            position=self._position(name),
            name=name.value,
            type=typ,
        )

    # ---------- statements ----------

    def parse_statement(self) -> Statement:
        if self._check("LBRACE"):
            return self.parse_block()

        if self._check("IF"):
            return self.parse_if()

        if self._check("WHILE"):
            return self.parse_while()

        if self._check("ASSERT"):
            return self.parse_assert()

        if self._check("ASSUME"):
            return self.parse_assume()

        if self._check("IDENT"):
            return self.parse_assignment()

        raise ParseError("expected statement", self._peek())

    def parse_block(self) -> Block:
        start = self._expect("LBRACE")

        statements: List[Statement] = []

        while not self._check("RBRACE") and not self._at_end():
            start_pos = self.pos

            try:
                statement = self.parse_statement()
                statements.append(statement)

            except ParseError as error:
                # Keep every error. Do not re-raise only the first one.
                self.errors.append(error)
                self._synchronize(in_block=True)

            self._ensure_progress(start_pos, in_block=True)

        if self._check("RBRACE"):
            self._advance()
        else:
            # Report the missing brace without discarding earlier errors.
            self.errors.append(
                ParseError(
                    "unexpected end of input, expected one of ('RBRACE',)"
                )
            )

        # Return the partial block so parsing can continue.
        return Block(stmts=statements, position=self._position(start))

    def parse_if(self) -> If:
        start = self._expect("IF")
        self._expect("LPAREN")

        condition = self.parse_condition()

        self._expect("RPAREN")
        then_branch = self.parse_statement()

        else_branch = None
        if self._match("ELSE"):
            else_branch = self.parse_statement()

        return If(
            position=self._position(start),
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
        )

    def parse_while(self) -> While:
        start = self._expect("WHILE")
        self._expect("LPAREN")

        condition = self.parse_condition()

        self._expect("RPAREN")

        invariant = None
        if self._match("INVARIANT"):
            invariant = self.parse_predicate()

        body = self.parse_statement()

        return While(
            position=self._position(start),
            condition=condition,
            invariant=invariant,
            body=body,
        )

    def parse_assert(self) -> Assert:
        start = self._expect("ASSERT")
        predicate = self.parse_predicate()
        self._expect("SEMICOLON")

        return Assert(predicate=predicate, position=self._position(start))

    def parse_assume(self) -> Assume:
        start = self._expect("ASSUME")
        predicate = self.parse_predicate()
        self._expect("SEMICOLON")

        return Assume(predicate=predicate, position=self._position(start))

    def parse_assignment(self) -> Assign:
        start = self._peek()
        targets = [self.parse_lvalue()]

        while self._match("COMMA"):
            targets.append(self.parse_lvalue())

        self._expect("ASSIGN")
        value = self.parse_condition()
        self._expect("SEMICOLON")

        return Assign(
            position=self._position(start),
            targets=targets,
            value=value,
        )

    def parse_lvalue(self):
        name = self._expect("IDENT")

        if self._match("LBRACKET"):
            index = self.parse_condition()
            self._expect("RBRACKET")

            return ArrayAccess(
                position=self._position(name),
                array=Var(name.value, position=self._position(name)),
                index=index,
            )

        return Var(name.value, position=self._position(name))

    # ---------- arithmetic expressions ----------

    def parse_expr(self) -> Expr:
        left = self.parse_term()

        while self._check("PLUS", "MINUS"):
            operator = self._advance()
            right = self.parse_term()

            left = BinOp(
                position=self._position(operator),
                op=operator.value,
                left=left,
                right=right,
            )

        return left

    def parse_term(self) -> Expr:
        left = self.parse_factor()

        while self._check("STAR", "SLASH"):
            operator = self._advance()
            right = self.parse_factor()

            left = BinOp(
                position=self._position(operator),
                op=operator.value,
                left=left,
                right=right,
            )

        return left

    def parse_factor(self) -> Expr:
        if self._check("MINUS"):
            start = self._advance()
            return UnOp(
                position=self._position(start),
                op="-",
                operand=self.parse_factor(),
            )

        if self._match("LPAREN"):
            expression = self.parse_condition()
            self._expect("RPAREN")
            return expression

        if self._check("TRUE"):
            token = self._advance()
            return BoolLit(True, position=self._position(token))

        if self._check("FALSE"):
            token = self._advance()
            return BoolLit(False, position=self._position(token))

        if self._check("INT"):
            token = self._advance()
            return IntLit(int(token.value), position=self._position(token))

        if self._check("IDENT"):
            name = self._advance()

            if self._match("LPAREN"):
                args: List[Expr] = []

                if not self._check("RPAREN"):
                    args.append(self.parse_condition())

                    while self._match("COMMA"):
                        args.append(self.parse_condition())

                self._expect("RPAREN")

                return FunctionCall(
                    position=self._position(name),
                    name=name.value,
                    args=args,
                )

            if self._match("LBRACKET"):
                index = self.parse_condition()
                self._expect("RBRACKET")

                return ArrayAccess(
                    position=self._position(name),
                    array=Var(name.value, position=self._position(name)),
                    index=index,
                )

            return Var(name.value, position=self._position(name))

        raise ParseError("expected expression", self._peek())

    # ---------- conditions and predicates ----------

    def parse_predicate(self) -> Condition:
        return self.parse_condition()

    def parse_condition(self) -> Condition:
        return self.parse_impl()

    def parse_impl(self) -> Condition:
        left = self.parse_or()

        if self._check("IMPLIES"):
            operator = self._advance()
            right = self.parse_impl()

            return LogicalOp(
                position=self._position(operator),
                op="->",
                left=left,
                right=right,
            )

        return left

    def parse_or(self) -> Condition:
        left = self.parse_and()

        while self._check("OR"):
            operator = self._advance()
            right = self.parse_and()

            left = LogicalOp(
                position=self._position(operator),
                op="or",
                left=left,
                right=right,
            )

        return left

    def parse_and(self) -> Condition:
        left = self.parse_not()

        while self._check("AND"):
            operator = self._advance()
            right = self.parse_not()

            left = LogicalOp(
                position=self._position(operator),
                op="and",
                left=left,
                right=right,
            )

        return left

    def parse_not(self) -> Condition:
        if self._check("NOT"):
            token = self._advance()
            return Not(operand=self.parse_not(), position=self._position(token))

        return self.parse_comparison()

    def parse_comparison(self) -> Condition:
        if self._check("FORALL", "EXISTS"):
            return self.parse_quantifier()

        # Parentheses are handled uniformly by parse_factor().
        left = self.parse_expr()

        if self._check("EQ", "NE", "LE", "GE", "LT", "GT"):
            operator = self._advance()
            right = self.parse_expr()

            return Comparison(
                position=self._position(operator),
                op=operator.value,
                left=left,
                right=right,
            )

        # Whether a bare expression is bool is decided by HW3, not the parser.
        return left

    def parse_quantifier(self) -> Quantifier:
        kind = self._expect("FORALL", "EXISTS")

        self._expect("LPAREN")
        variable = self.parse_param()
        self._expect("BAR")

        body = self.parse_predicate()

        self._expect("RPAREN")

        return Quantifier(
            position=self._position(kind),
            kind=kind.value,
            var=variable,
            body=body,
        )


# ---------- public API ----------

def parse_tokens(
    tokens: List[Token],
) -> Tuple[Module, List[ParseError]]:
    """Parse tokens and return (Module, errors).

    The module may be partial if syntax errors occur.
    """
    if not tokens:
        return Module(), [ParseError("empty input")]

    parser = Parser(tokens)
    return parser.parse()


def parse_text(text: str) -> Tuple[Module, List[ParseError]]:
    """Tokenize and parse source text."""
    try:
        tokens = tokenize(text)
    except LexerError as error:
        token = Token(
            "",
            "",
            error.line,
            error.column,
            error.offset,
        )
        return Module(), [ParseError(f"lexer: {error}", token)]

    return parse_tokens(tokens)


def parse_file(path: str) -> Tuple[Module, List[ParseError]]:
    """Read a UTF-8 file and parse its contents."""
    from pathlib import Path

    text = Path(path).read_text(encoding="utf-8")
    return parse_text(text)
