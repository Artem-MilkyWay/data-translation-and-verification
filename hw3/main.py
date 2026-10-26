#!/usr/bin/env python3.13
"""CLI for Funny (HW3): semantic checks and annotated AST."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lexer import tokenize, LexerError
from semantic import analyze_text


def cmd_tokens(path: Path) -> int:
    text = sys.stdin.read() if str(path) == "-" else path.read_text(encoding="utf-8")
    try:
        tokens = tokenize(text)
    except LexerError as e:
        print(f"Lexer error: {e}", file=sys.stderr)
        return 1
    for t in tokens:
        print(f"{t.line}:{t.column}\t{t.type}\t{t.value!r}")
    return 0


def cmd_ast(path: Path, pretty: bool = True) -> int:
    text = sys.stdin.read() if str(path) == "-" else path.read_text(encoding="utf-8")
    result = analyze_text(text)

    if result.errors:
        for e in result.errors:
            print(
                f"{e.position.line}:{e.position.column}: {e.code}: {e.message}",
                file=sys.stderr,
            )

    data = result.to_dict()
    if pretty:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(data, ensure_ascii=False))

    return 1 if result.errors else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Funny HW3: semantic checks and annotated AST")
    ap.add_argument("file", nargs="?", help="source .funny file, or - for stdin")
    ap.add_argument("--ast", action="store_true", help="print annotated AST and errors as JSON (default)")
    ap.add_argument("--tokens", action="store_true", help="print token stream")
    ap.add_argument("--compact", action="store_true", help="compact JSON")
    ap.add_argument("--test", action="store_true", help="run test suite")
    args = ap.parse_args()

    if args.test:
        from tests.run_tests import main as test_main
        return test_main()

    if args.file is None:
        ap.print_help()
        return 2

    path = Path(args.file)
    try:
        if args.tokens:
            return cmd_tokens(path)
        return cmd_ast(path, pretty=not args.compact)
    except (OSError, UnicodeError) as e:
        print(f"Cannot read source: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
