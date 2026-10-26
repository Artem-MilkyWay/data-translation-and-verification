"""Lexer adapter: wraps HW1 scan() and attaches line/column/offset positions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from automata import (
    build_combined_nfa,
    nfa_to_dfa,
    complete_dfa,
    trim_unreachable,
    hopcroft_minimize,
    scan,
)
from lexer_spec import RULES, ALPHABET


@dataclass
class Token:
    type: str
    value: str
    line: int
    column: int
    offset: int

    def __repr__(self) -> str:
        return f"Token({self.type!r}, {self.value!r}, {self.line}:{self.column})"


class LexerError(Exception):
    def __init__(self, message: str, line: int, column: int, offset: int):
        super().__init__(message)
        self.line = line
        self.column = column
        self.offset = offset
        self.message = message

    def __str__(self) -> str:
        return f"{self.message} at {self.line}:{self.column}"


_dfa = None


def _get_dfa():
    global _dfa
    if _dfa is None:
        nfa = build_combined_nfa(RULES)
        dfa = nfa_to_dfa(nfa, ALPHABET)
        dfa = complete_dfa(dfa)
        dfa = trim_unreachable(dfa)
        _dfa = hopcroft_minimize(dfa)
    return _dfa


def tokenize(text: str) -> List[Token]:
    """Tokenize source text. Raises LexerError on illegal characters."""
    dfa = _get_dfa()
    raw = scan(dfa, text)
    tokens: List[Token] = []
    # scan() supplies original offsets, including skipped comments/whitespace.
    # Advance the line/column cursor once through the source.
    cursor, line, col = 0, 1, 1
    for item in raw:
        pos = item["position"]
        while cursor < pos:
            if text[cursor] == "\n":
                line, col = line + 1, 1
            else:
                col += 1
            cursor += 1
        if "error" in item:
            raise LexerError(
                f"unexpected character {item['error']!r}", line, col, pos,
            )
        tokens.append(Token(item["kind"], item["lexeme"], line, col, pos))
    return tokens


def tokenize_file(path: str | Path) -> List[Token]:
    text = Path(path).read_text(encoding="utf-8")
    return tokenize(text)
