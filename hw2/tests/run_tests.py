#!/usr/bin/env python3
"""Positive / negative test runner for HW2 parser (panic mode)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from parser import parse_text, ParseError


POSITIVE = ROOT / "tests" / "positive"
NEGATIVE = ROOT / "tests" / "negative"


def run_positive() -> list[str]:
    failures = []
    files = sorted(POSITIVE.glob("*.funny"))
    if not files:
        failures.append("no positive tests found")
        return failures
    for path in files:
        text = path.read_text(encoding="utf-8")
        mod, errors = parse_text(text)
        if errors:
            failures.append(f"{path.name}: unexpected errors: {errors}")
            print(f"  FAIL  {path.name}: {errors[0]}")
            continue
        d = mod.to_dict()
        if d.get("kind") != "Module":
            failures.append(f"{path.name}: root is not Module")
            print(f"  FAIL  {path.name}: root is not Module")
            continue
        print(f"  PASS  {path.name}")
    return failures


def run_negative() -> list[str]:
    failures = []
    files = sorted(NEGATIVE.glob("*.funny"))
    if not files:
        failures.append("no negative tests found")
        return failures
    for path in files:
        text = path.read_text(encoding="utf-8")
        mod, errors = parse_text(text)
        if not errors:
            failures.append(f"{path.name}: expected error, but parse succeeded")
            print(f"  FAIL  {path.name}: expected error")
            continue
        print(f"  PASS  {path.name}: {errors[0]}")
    return failures


def check_sum_example() -> list[str]:
    failures = []
    path = ROOT / "examples" / "sum.funny"
    if not path.exists():
        return ["examples/sum.funny missing"]
    text = path.read_text(encoding="utf-8")
    mod, errors = parse_text(text)
    if errors:
        failures.append(f"sum.funny: unexpected errors: {errors}")
        print(f"  FAIL  examples/sum.funny: {errors[0]}")
        return failures
    d = mod.to_dict()
    try:
        assert d["kind"] == "Module"
        assert len(d["functions"]) == 1
        f = d["functions"][0]
        assert f["name"] == "sum"
        assert f["params"][0]["name"] == "a"
        assert f["returns"][0]["name"] == "r"
        body = f["body"]
        assert body["kind"] == "Block"
        assert body["stmts"][0]["kind"] == "Assign"
        print("  PASS  examples/sum.funny structure")
    except AssertionError as e:
        failures.append(f"sum.funny: assertion {e}")
        print(f"  FAIL  examples/sum.funny: assertion {e}")
    return failures


def main() -> int:
    print("=== Positive tests ===")
    fails = run_positive()
    print("=== Negative tests ===")
    fails += run_negative()
    print("=== Example check ===")
    fails += check_sum_example()
    print()
    if fails:
        print(f"FAILED ({len(fails)}):")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("All tests PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())