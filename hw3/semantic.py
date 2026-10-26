"""Name resolution and strict type checking for the basic HW3 subset of Funny."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import ast_nodes as ast
from lexer import Token
from parser import parse_text


@dataclass(frozen=True)
class Type:
    kind: str
    params: tuple[Type, ...] = ()
    results: tuple[Type, ...] = ()

    def to_dict(self):
        if self.kind == "func":
            return {"kind": "func", "params": [t.to_dict() for t in self.params],
                    "returns": [t.to_dict() for t in self.results]}
        if self.kind == "tuple":
            return {"kind": "tuple", "items": [t.to_dict() for t in self.results]}
        return self.kind

    def __str__(self):
        if self.kind == "func":
            return f"func({', '.join(map(str, self.params))}) -> ({', '.join(map(str, self.results))})"
        if self.kind == "tuple":
            return f"({', '.join(map(str, self.results))})"
        return self.kind


INT, BOOL, ARRAY, ERROR = (Type(name) for name in ("int", "bool", "int[]", "error"))


def unify(left: Type, right: Type) -> Type:
    """Concrete structural unification; no variables, inference, or coercions.

    ERROR propagates silently to avoid repeated diagnostics for one bad subtree.
    Function signatures and result tuples unify structurally through dataclass
    equality, including their arity, parameter types, and return types.
    """
    return left if left == right and left != ERROR else ERROR


@dataclass
class Diagnostic:
    phase: str
    code: str
    message: str
    position: ast.Position

    def to_dict(self):
        return {"phase": self.phase, "code": self.code, "message": self.message,
                **self.position.to_dict()}


@dataclass
class Symbol:
    id: int
    name: str
    kind: str
    type: Type
    position: ast.Position

    def to_dict(self):
        return {"id": self.id, "name": self.name, "kind": self.kind,
                "type": self.type.to_dict(), "position": self.position.to_dict()}


class Scope:
    def __init__(self, parent: Optional[Scope] = None):
        self.parent = parent
        self.symbols: dict[str, Symbol] = {}

    def lookup(self, name: str) -> Optional[Symbol]:
        if name in self.symbols:
            return self.symbols[name]
        return self.parent.lookup(name) if self.parent else None


@dataclass
class AnalysisResult:
    ast: ast.Module
    errors: list[Diagnostic]
    symbols: list[Symbol]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self):
        return {"format_version": 1, "ok": self.ok, "ast": self.ast.to_dict(),
                "symbols": [s.to_dict() for s in self.symbols],
                "errors": [e.to_dict() for e in self.errors]}


class Analyzer:
    def __init__(self):
        self.errors: list[Diagnostic] = []
        self.symbols: list[Symbol] = []
        self.globals = Scope()
        self.future: dict[str, ast.Position] = {}

    def error(self, node: ast.Node, code: str, message: str):
        assert node.position is not None, "parser must attach source positions"
        self.errors.append(Diagnostic("semantic", code, message, node.position))

    def declared_type(self, node: ast.VarDef) -> Type:
        if node.type is None:
            self.error(node, "E_MISSING_TYPE", f"Variable '{node.name}' requires an explicit type annotation")
            return ERROR
        if isinstance(node.type, ast.TypeInt):
            return INT
        if isinstance(node.type, ast.TypeBool):
            return BOOL
        if isinstance(node.type, ast.TypeArray):
            return ARRAY
        raise TypeError(f"Unsupported type node: {type(node.type).__name__}")

    def define(self, scope: Scope, node: ast.Node, typ: Type, kind: str):
        node.inferred_type = typ
        previous = scope.symbols.get(node.name)
        if previous:
            self.error(node, "E_DUPLICATE_NAME",
                       f"Duplicate declaration of '{node.name}'; first declared at "
                       f"{previous.position.line}:{previous.position.column}")
            return
        symbol = Symbol(len(self.symbols) + 1, node.name, kind, typ, node.position)
        scope.symbols[node.name] = symbol
        self.symbols.append(symbol)
        node.symbol_id = symbol.id

    def resolve(self, scope: Scope, node: ast.Node) -> Optional[Symbol]:
        symbol = scope.lookup(node.name)
        if symbol:
            node.symbol_id = symbol.id
            return symbol
        upcoming = self.future.get(node.name)
        if upcoming and upcoming.offset > node.position.offset:
            self.error(node, "E_BEFORE_DECLARATION",
                       f"Name '{node.name}' is used before its declaration at {upcoming.line}:{upcoming.column}")
        else:
            self.error(node, "E_UNKNOWN_NAME", f"Unknown name '{node.name}': no visible declaration")
        return None

    def expect(self, node: ast.Node, actual: Type, expected: Type, context: str) -> bool:
        if actual == ERROR or expected == ERROR:
            return False
        if unify(actual, expected) == ERROR:
            self.error(node, "E_TYPE_MISMATCH", f"{context}: expected {expected}, got {actual}")
            return False
        return True

    def analyze(self, module: ast.Module) -> AnalysisResult:
        # HW2 stores functions/formulas separately. Restore source order using offsets.
        declarations = sorted(module.functions + module.formulas, key=lambda n: n.position.offset)
        for decl in declarations:
            self.future.setdefault(decl.name, decl.position)
        for decl in declarations:
            params = tuple(self.declared_type(p) for p in decl.params)
            results = (tuple(self.declared_type(r) for r in decl.returns)
                       if isinstance(decl, ast.Function) else (BOOL,))
            signature = Type("func", params, results)
            kind = "function" if isinstance(decl, ast.Function) else "formula"
            # Define before body to allow direct recursion, but not forward calls.
            self.define(self.globals, decl, signature, kind)
            scope = Scope(self.globals)
            for param, typ in zip(decl.params, params):
                self.define(scope, param, typ, "parameter")
            if isinstance(decl, ast.Formula):
                self.expect(decl.body, self.expr(decl.body, scope), BOOL, "Formula body")
                continue
            if decl.requires is not None:
                self.expect(decl.requires, self.expr(decl.requires, scope), BOOL, "requires")
            for result, typ in zip(decl.returns, results):
                self.define(scope, result, typ, "return")
            if decl.ensures is not None:
                self.expect(decl.ensures, self.expr(decl.ensures, scope), BOOL, "ensures")
            for local in decl.uses:
                self.define(scope, local, self.declared_type(local), "local")
            self.statement(decl.body, scope)
        return AnalysisResult(module, self.errors, self.symbols)

    def expr(self, node: ast.Expr, scope: Scope, allow_tuple: bool = False) -> Type:
        typ = self._expr(node, scope)
        if typ.kind == "tuple" and not allow_tuple:
            self.error(node, "E_MULTI_VALUE", "A function with multiple results is only valid as the right side of a multiple assignment")
            typ = ERROR
        node.inferred_type = typ
        return typ

    def _expr(self, node: ast.Expr, scope: Scope) -> Type:
        if isinstance(node, ast.IntLit):
            return INT
        if isinstance(node, ast.BoolLit):
            return BOOL
        if isinstance(node, ast.Var):
            symbol = self.resolve(scope, node)
            if symbol is None:
                return ERROR
            if symbol.type.kind == "func":
                self.error(node, "E_FUNCTION_VALUE", f"'{node.name}' must be called; functions are not first-class values")
                return ERROR
            return symbol.type
        if isinstance(node, ast.ArrayAccess):
            base, index = self.expr(node.array, scope), self.expr(node.index, scope)
            a = self.expect(node.array, base, ARRAY, "Array access")
            b = self.expect(node.index, index, INT, "Array index")
            return INT if a and b else ERROR
        if isinstance(node, ast.BinOp):
            left, right = self.expr(node.left, scope), self.expr(node.right, scope)
            a = self.expect(node.left, left, INT, f"Left operand of '{node.op}'")
            b = self.expect(node.right, right, INT, f"Right operand of '{node.op}'")
            return INT if a and b else ERROR
        if isinstance(node, ast.UnOp):
            operand = self.expr(node.operand, scope)
            return INT if self.expect(node.operand, operand, INT, "Unary '-'") else ERROR
        if isinstance(node, ast.Comparison):
            left, right = self.expr(node.left, scope), self.expr(node.right, scope)
            if left == ERROR or right == ERROR:
                return ERROR
            if node.op in {"==", "!="}:
                return BOOL if self.expect(node.right, right, left, f"Comparison '{node.op}'") else ERROR
            a = self.expect(node.left, left, INT, f"Left operand of '{node.op}'")
            b = self.expect(node.right, right, INT, f"Right operand of '{node.op}'")
            return BOOL if a and b else ERROR
        if isinstance(node, ast.LogicalOp):
            left, right = self.expr(node.left, scope), self.expr(node.right, scope)
            a = self.expect(node.left, left, BOOL, f"Left operand of '{node.op}'")
            b = self.expect(node.right, right, BOOL, f"Right operand of '{node.op}'")
            return BOOL if a and b else ERROR
        if isinstance(node, ast.Not):
            operand = self.expr(node.operand, scope)
            return BOOL if self.expect(node.operand, operand, BOOL, "Operand of 'not'") else ERROR
        if isinstance(node, ast.Quantifier):
            inner = Scope(scope)
            self.define(inner, node.var, self.declared_type(node.var), "quantifier")
            body = self.expr(node.body, inner)
            return BOOL if self.expect(node.body, body, BOOL, f"Body of '{node.kind}'") else ERROR
        if isinstance(node, (ast.FunctionCall, ast.FormulaRef)):
            symbol = self.resolve(scope, node)
            # Check every argument even if the callee is unknown or arity is wrong.
            actual = [self.expr(arg, scope) for arg in node.args]
            if symbol is None:
                return ERROR
            if symbol.type.kind != "func":
                self.error(node, "E_NOT_CALLABLE", f"'{node.name}' has type {symbol.type} and cannot be called")
                return ERROR
            signature = symbol.type
            valid = True
            if len(actual) != len(signature.params):
                self.error(node, "E_ARGUMENT_COUNT", f"Call to '{node.name}': expected {len(signature.params)} arguments, got {len(actual)}")
                valid = False
            for i, (arg, got, wanted) in enumerate(zip(node.args, actual, signature.params), 1):
                if not self.expect(arg, got, wanted, f"Argument {i} of '{node.name}'"):
                    valid = False
            if ERROR in actual:
                valid = False
            if not valid:
                return ERROR
            return signature.results[0] if len(signature.results) == 1 else Type("tuple", results=signature.results)
        raise TypeError(f"Unsupported expression: {type(node).__name__}")

    def statement(self, node: ast.Statement, scope: Scope):
        if isinstance(node, ast.Block):
            inner = Scope(scope)
            for child in node.stmts:
                self.statement(child, inner)
        elif isinstance(node, ast.Assign):
            actual = self.expr(node.value, scope, allow_tuple=True)
            targets = [self.expr(target, scope) for target in node.targets]
            if actual == ERROR:
                return
            values = actual.results if actual.kind == "tuple" else (actual,)
            if len(values) != len(targets):
                self.error(node, "E_RESULT_COUNT", f"Assignment has {len(targets)} targets, but the right side produces {len(values)} values")
            for i, (target, expected, got) in enumerate(zip(node.targets, targets, values), 1):
                self.expect(target, got, expected, f"Assignment target {i}")
        elif isinstance(node, ast.If):
            self.expect(node.condition, self.expr(node.condition, scope), BOOL, "if condition")
            self.statement(node.then_branch, Scope(scope))
            if node.else_branch is not None:
                self.statement(node.else_branch, Scope(scope))
        elif isinstance(node, ast.While):
            self.expect(node.condition, self.expr(node.condition, scope), BOOL, "while condition")
            if node.invariant is not None:
                self.expect(node.invariant, self.expr(node.invariant, scope), BOOL, "Loop invariant")
            self.statement(node.body, Scope(scope))
        elif isinstance(node, (ast.Assert, ast.Assume)):
            self.expect(node.predicate, self.expr(node.predicate, scope), BOOL, type(node).__name__)
        else:
            raise TypeError(f"Unsupported statement: {type(node).__name__}")


def analyze_text(source: str) -> AnalysisResult:
    """Return positioned, annotated AST, symbols and all available diagnostics.

    Semantic analysis runs on syntactically valid input only. On syntax/lexical
    errors the partial parser AST is returned without semantic annotations.
    """
    module, parse_errors = parse_text(source)
    if parse_errors:
        eof = ast.Position(source.count("\n") + 1, len(source.rsplit("\n", 1)[-1]) + 1, len(source))
        errors = []
        for error in parse_errors:
            token: Optional[Token] = error.token
            pos = ast.Position(token.line, token.column, token.offset) if token else eof
            phase = "lexer" if error.message.startswith("lexer:") else "parser"
            code = "E_LEXER" if phase == "lexer" else "E_SYNTAX"
            errors.append(Diagnostic(phase, code, error.message, pos))
        return AnalysisResult(module, errors, [])
    return Analyzer().analyze(module)
