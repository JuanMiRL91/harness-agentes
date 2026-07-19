#!/usr/bin/env python3
"""
harness/check_docs.py - Deterministic documentation check.

Detects public symbols added/removed in the session diff (working tree +
staged vs HEAD) in core/*.py and ui/common.py, and cross-checks them against
the mentions in harness/docs/architecture.md, harness/docs/data-models.md and
CLAUDE.md, listing exactly what is missing or leftover. A new symbol only
needs to be mentioned in ONE of the docs (the detail lives in architecture.md
or data-models.md; CLAUDE.md stays minimal); a removed symbol must not remain
mentioned in ANY.

It also cross-checks the real list of project modules (core/*.py, ui/*.py,
ui/pages/*.py) against README.md: each module must appear by name in the
Structure section. This cross-check runs every time the script is invoked (it
does not depend on the diff), so accumulated drift surfaces in the first
session that touches code.

It is an informative check: it must never raise an uncontrolled exception nor
block close.sh due to an unexpected git/IO failure (exit 0 in that case).
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"

CLAUDE_MD = ROOT / "CLAUDE.md"
README_MD = ROOT / "README.md"
ARCHITECTURE_MD = ROOT / "harness" / "docs" / "architecture.md"
DATA_MODELS_MD = ROOT / "harness" / "docs" / "data-models.md"

DOCS = (
    ("architecture.md", ARCHITECTURE_MD),
    ("data-models.md", DATA_MODELS_MD),
    ("CLAUDE.md", CLAUDE_MD),
)


def public_symbols(source: str) -> set[str]:
    """Module-level public symbols: def/async def, class and assignments to
    UPPER_CASE_NAMES (AnnAssign included). Excludes any name starting with
    '_'. Returns set() if the source does not parse (SyntaxError)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    symbols: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                symbols.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    if target.id.isupper():
                        symbols.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and not target.id.startswith("_"):
                if target.id.isupper():
                    symbols.add(target.id)

    return symbols


def mentions(doc_text: str, symbol: str) -> bool:
    """True if doc_text mentions symbol as a whole word (\\b + re.escape)."""
    pattern = r"\b" + re.escape(symbol) + r"\b"
    return re.search(pattern, doc_text) is not None


def project_modules() -> list[str]:
    """Relative paths (with /) of the modules README.md must mention:
    core/*.py, ui/*.py and ui/pages/*.py, excluding private (_*) and __init__."""
    paths: list[str] = []
    for pattern in ("core/*.py", "ui/*.py", "ui/pages/*.py"):
        for p in sorted(ROOT.glob(pattern)):
            if p.name.startswith("_"):
                continue
            paths.append(p.relative_to(ROOT).as_posix())
    return paths


def modules_missing_from_readme() -> list[str]:
    """Project modules whose file name does not appear in README.md."""
    if not README_MD.exists():
        return []
    text = README_MD.read_text(encoding="utf-8")
    return [
        path
        for path in project_modules()
        if not mentions(text, path.rsplit("/", 1)[-1])
    ]


def diff_symbols(old_source: str, new_source: str) -> tuple[set[str], set[str]]:
    """Returns (added, removed) between old_source and new_source."""
    before = public_symbols(old_source)
    after = public_symbols(new_source)
    added = after - before
    removed = before - after
    return added, removed


def changed_files() -> list[tuple[str, str]]:
    """Parses `git status --porcelain -- core ui` and returns (status, path)
    only for .py under core/ or exactly ui/common.py."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "core", "ui"],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git status failed: {result.stderr.strip()}")

    changed: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        status = line[:2]
        rest = line[3:]

        if status.startswith("R"):
            # Format: "old -> new"
            if " -> " in rest:
                path = rest.split(" -> ", 1)[1].strip()
            else:
                path = rest.strip()
        else:
            path = rest.strip()

        # Remove quotes if git quoted the path (paths with spaces/unicode)
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]

        is_core_py = path.startswith("core/") and path.endswith(".py")
        is_ui_common = path == "ui/common.py"
        if is_core_py or is_ui_common:
            changed.append((status.strip(), path))

    return changed


def head_content(path: str) -> str:
    """Returns the content of path at HEAD; '' if it fails (new file)."""
    result = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def main() -> int:
    try:
        findings: list[str] = []

        for path in modules_missing_from_readme():
            findings.append(
                f"{YELLOW}[WARN]{NC} README.md: module {path} not mentioned in the Structure section"
            )

        changed = changed_files()

        if not changed and not findings:
            print(f"{GREEN}[OK]{NC} No changes in core/ or ui/common.py - nothing to cross-check; README.md covers all modules")
            return 0

        added_by_file: dict[str, set[str]] = {}
        removed_by_file: dict[str, set[str]] = {}

        for status, path in changed:
            old_source = head_content(path)

            if status == "D":
                new_source = ""
            else:
                absolute_path = ROOT / path
                if not absolute_path.exists():
                    continue
                new_source = absolute_path.read_text(encoding="utf-8")

            added, removed = diff_symbols(old_source, new_source)
            if added:
                added_by_file[path] = added
            if removed:
                removed_by_file[path] = removed

        docs = {}
        for name, doc_path in DOCS:
            if doc_path.exists():
                docs[name] = doc_path.read_text(encoding="utf-8")
            else:
                docs[name] = ""
                print(f"{YELLOW}[WARN]{NC} {doc_path.relative_to(ROOT)} not found, treated as empty")

        for path, symbols in sorted(added_by_file.items()):
            for symbol in sorted(symbols):
                if not any(mentions(text, symbol) for text in docs.values()):
                    findings.append(
                        f"{YELLOW}[WARN]{NC} {path}: new symbol '{symbol}' not mentioned in any doc "
                        f"(document it in architecture.md or, if it is data schema, in data-models.md)"
                    )

        for path, symbols in sorted(removed_by_file.items()):
            for symbol in sorted(symbols):
                for doc_name, text in docs.items():
                    if mentions(text, symbol):
                        findings.append(
                            f"{YELLOW}[WARN]{NC} {path}: removed symbol '{symbol}' still mentioned in {doc_name}"
                        )

        if not findings:
            print(f"{GREEN}[OK]{NC} Public symbols of the diff aligned with architecture.md / data-models.md / CLAUDE.md; README.md covers all modules")
            return 0

        for line in findings:
            print(line)

        print()
        print(f"{RED}[FAIL]{NC} {len(findings)} documentation finding(s) pending review.")
        return 1

    except Exception as e:  # noqa: BLE001 - informative check, must never break close.sh
        print(f"[INFO] check_docs could not complete: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
