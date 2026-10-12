#!/usr/bin/env python3
"""CLI for Funny LL(1) parser (HW2) with panic-mode recovery."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lexer import tokenize, LexerError
from parser import parse_text, ParseError


def cmd_tokens(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    try:
        tokens = tokenize(text)
    except LexerError as e:
        print(f"Lexer error: {e}", file=sys.stderr)
        return 1
    for t in tokens:
        print(f"{t.line}:{t.column}\t{t.type}\t{t.value!r}")
    return 0


def cmd_ast(path: Path, pretty: bool = True) -> int:
    text = path.read_text(encoding="utf-8")
    mod, errors = parse_text(text)

    if errors:
        for e in errors:
            print(f"Parse error: {e}", file=sys.stderr)

    if mod is None or not mod.functions and not mod.formulas:
        # nothing parsed at all
        return 1

    data = mod.to_dict()
    if pretty:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(data, ensure_ascii=False))

    return 1 if errors else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Funny HW2: LL(1) parser with panic mode")
    ap.add_argument("file", nargs="?", help="source .funny file")
    ap.add_argument("--ast", action="store_true", help="print AST as JSON")
    ap.add_argument("--tokens", action="store_true", help="print token stream")
    ap.add_argument("--compact", action="store_true", help="compact JSON")
    ap.add_argument("--test", action="store_true", help="run test suite")
    args = ap.parse_args()

    if args.test:
        from tests.run_tests import main as test_main
        return test_main()

    if args.file is None:
        ap.print_help()
        return 0

    path = Path(args.file)
    if not path.exists():
        print(f"file not found: {path}", file=sys.stderr)
        return 1

    if args.tokens:
        return cmd_tokens(path)
    return cmd_ast(path, pretty=not args.compact)


if __name__ == "__main__":
    raise SystemExit(main())