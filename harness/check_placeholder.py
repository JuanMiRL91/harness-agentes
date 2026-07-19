#!/usr/bin/env python3
"""Detects known placeholder/erroneous text in core/ and ui/ string literals.

Typical origin: filler text that reaches production without anyone noticing.
This check walks the string literals (f-strings included) of core/ and ui/ by
AST and fails if they contain any blacklisted term.

Stdlib only. Exit 0 if clean, 1 if there are findings.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

GREEN = "\033[0;32m"
RED = "\033[0;31m"
NC = "\033[0m"

# Terms that must never appear in a production string.
# (term, case_sensitive)
FORBIDDEN = [
    ("lorem ipsum", False),     # classic filler text
    ("TODO:", True),            # pending marker inside a visible literal
    ("FIXME", True),
]

SCAN_DIRS = ["core", "ui"]


def _strings_of(tree: ast.AST):
    """Yields (lineno, value) for each str literal in the tree, f-strings included."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


def main() -> int:
    findings = []
    for d in SCAN_DIRS:
        for py in sorted((ROOT / d).rglob("*.py")):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"))
            except SyntaxError as e:
                findings.append((py, e.lineno or 0, f"SyntaxError: {e.msg}"))
                continue
            for lineno, value in _strings_of(tree):
                for term, case_sensitive in FORBIDDEN:
                    haystack = value if case_sensitive else value.lower()
                    needle = term if case_sensitive else term.lower()
                    if needle in haystack:
                        findings.append((py, lineno, f"contains '{term}'"))

    if findings:
        for py, lineno, reason in findings:
            rel = py.relative_to(ROOT)
            print(f"{RED}[FAIL]{NC}   {rel}:{lineno} — {reason}")
        print(f"{RED}[FAIL]{NC}   {len(findings)} literal(s) with placeholder/erroneous text")
        return 1

    print(f"{GREEN}[OK]{NC}   No placeholder text in core/ and ui/ literals")
    return 0


if __name__ == "__main__":
    sys.exit(main())
