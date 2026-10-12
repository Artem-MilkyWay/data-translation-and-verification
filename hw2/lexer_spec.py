# Funny token specification for HW1 + HW2.
# Rule order is the priority used when several rules accept the same
# longest lexeme. Lower priority number wins.
RULES = [
    ("WS",       r"[ \t\r\n]+", True),
    ("COMMENT",  r"//[^\n]*", True),

    # Keywords have higher priority than IDENT on equal-length matches.
    ("FUNCTION",  r"function", False),
    ("RETURNS",   r"returns", False),
    ("USES",      r"uses", False),
    ("WHILE",     r"while", False),
    ("IF",        r"if", False),
    ("ELSE",      r"else", False),
    ("TRUE",      r"true", False),
    ("FALSE",     r"false", False),
    ("ASSERT",    r"assert", False),
    ("ASSUME",    r"assume", False),
    ("INVARIANT", r"invariant", False),
    ("LENGTH",    r"length", False),
    # HW2 keywords
    ("REQUIRES",  r"requires", False),
    ("ENSURES",   r"ensures", False),
    ("FORALL",    r"forall", False),
    ("EXISTS",    r"exists", False),
    ("INT_TYPE",  r"int", False),
    ("AND",       r"and", False),
    ("OR",        r"or", False),
    ("NOT",       r"not", False),

    ("IDENT", r"[A-Za-z_][A-Za-z0-9_]*", False),
    ("INT",   r"0|[1-9][0-9]*", False),

    ("EQ",       r"==", False),
    ("NE",       r"!=", False),
    ("LE",       r"<=", False),
    ("GE",       r">=", False),
    ("IMPLIES",  r"->", False),
    ("PLUS",     r"\+", False),
    ("MINUS",    r"-", False),
    ("STAR",     r"\*", False),
    ("SLASH",    r"/", False),
    ("LT",       r"<", False),
    ("GT",       r">", False),
    ("ASSIGN",   r"=", False),
    ("COMMA",    r",", False),
    ("SEMICOLON",r";", False),
    ("COLON",    r":", False),
    ("BAR",      r"\|", False),
    ("LPAREN",   r"\(", False),
    ("RPAREN",   r"\)", False),
    ("LBRACKET", r"\[", False),
    ("RBRACKET", r"\]", False),
    ("LBRACE",   r"\{", False),
    ("RBRACE",   r"\}", False),
]

# ASCII is the complete input alphabet for the assignment.
ALPHABET = tuple(chr(i) for i in range(128))
