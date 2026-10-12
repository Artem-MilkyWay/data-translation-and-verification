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


def _line_col(text: str, offset: int) -> tuple[int, int]:
    """Return 1-based (line, column) for absolute offset."""
    line = 1
    col = 1
    for i, ch in enumerate(text):
        if i == offset:
            return line, col
        if ch == "\n":
            line += 1
            col = 1
        else:
            col += 1
    return line, col


def tokenize(text: str) -> List[Token]:
    """Tokenize source text. Raises LexerError on illegal characters."""
    dfa = _get_dfa()
    raw = scan(dfa, text)
    tokens: List[Token] = []
    # Reconstruct offsets: scan() does not return positions, so walk the text.
    i = 0
    for item in raw:
        if "error" in item:
            line, col = _line_col(text, item["position"])
            raise LexerError(
                f"unexpected character {item['error']!r}",
                line,
                col,
                item["position"],
            )
        kind = item["kind"]
        lexeme = item["lexeme"]
        # Find next occurrence of lexeme starting at i (skip was already filtered)
        pos = text.find(lexeme, i)
        if pos < 0:
            # Should not happen for well-formed scan output
            pos = i
        line, col = _line_col(text, pos)
        tokens.append(Token(kind, lexeme, line, col, pos))
        i = pos + len(lexeme)
    return tokens


def tokenize_file(path: str | Path) -> List[Token]:
    text = Path(path).read_text(encoding="utf-8")
    return tokenize(text)
