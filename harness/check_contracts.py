"""
Verifies that every symbol imported from core/ actually exists.
Scans ui/ (and scripts/) for core imports and calls attr/import to confirm.
Output: OK/FAIL list per symbol. Exit code 1 if there is any FAIL.
"""

import ast
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
UI_DIRS = [ROOT / "ui", ROOT / "scripts"]

GREEN = "\033[0;32m"
RED   = "\033[0;31m"
NC    = "\033[0m"


def ok(msg):   print(f"{GREEN}[OK]{NC}   {msg}")
def fail(msg): print(f"{RED}[FAIL]{NC} {msg}")


def collect_core_imports(path: Path) -> list[tuple[str, str, str]]:
    """
    Returns a list of (file, core_module, symbol) for each core.* import.
    Covers:
      - from core.X import a, b, c   → (file, "core.X", "a"), ...
      - from core import X           → (file, "core", "X")  — verified as a module
      - import core.X as alias       → (file, "core.X", None)
    """
    results = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return results

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if not module.startswith("core"):
                continue
            for alias in node.names:
                results.append((str(path.relative_to(ROOT)), module, alias.name))

        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("core"):
                    results.append((str(path.relative_to(ROOT)), alias.name, None))

    return results


def verify(file: str, module: str, symbol: str | None) -> bool:
    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError as e:
        fail(f"{file}: cannot import '{module}' — {e}")
        return False

    if symbol is None:
        ok(f"{file}: import {module}")
        return True

    if not hasattr(mod, symbol):
        # It may be a submodule (e.g.: from core import quotes → core.quotes)
        try:
            importlib.import_module(f"{module}.{symbol}")
            ok(f"{file}: {module}.{symbol} (submodule)")
            return True
        except ModuleNotFoundError:
            pass
        fail(f"{file}: '{module}' has no '{symbol}'")
        return False

    ok(f"{file}: {module}.{symbol}")
    return True


def scan_module_dot_attr(path: Path) -> list[tuple[str, str, str]]:
    """
    Detects uses of the `alias.method(` pattern where alias was imported
    as `from core import alias`. Example: `quotes.current_price(`.
    """
    results = []
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except SyntaxError:
        return results

    # Maps alias → full core module for imports like `from core import X`
    alias_to_module: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "core":
                for alias in node.names:
                    name = alias.asname or alias.name
                    alias_to_module[name] = f"core.{alias.name}"

    # Looks for alias.attr(...) calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                alias = node.value.id
                if alias in alias_to_module:
                    results.append((
                        str(path.relative_to(ROOT)),
                        alias_to_module[alias],
                        node.attr,
                    ))

    return results


def main() -> int:
    sys.path.insert(0, str(ROOT))

    all_checks: list[tuple[str, str, str | None]] = []

    for ui_dir in UI_DIRS:
        if not ui_dir.exists():
            continue
        for py_file in ui_dir.rglob("*.py"):
            all_checks.extend(collect_core_imports(py_file))
            all_checks.extend(scan_module_dot_attr(py_file))

    if not all_checks:
        print("No core/ imports found. Nothing to verify.")
        return 0

    # Deduplicate
    seen = set()
    unique = []
    for item in all_checks:
        key = (item[1], item[2])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    failures = 0
    for file, module, symbol in unique:
        if not verify(file, module, symbol):
            failures += 1

    print()
    if failures:
        print(f"{RED}FAIL {failures} broken contract(s). Review core/ before continuing.{NC}")
    else:
        print(f"{GREEN}OK All UI<->core contracts verified.{NC}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
