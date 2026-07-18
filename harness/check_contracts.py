"""
Verifica que todos los símbolos importados desde core/ existen realmente.
Escanea ui/ (y scripts/) buscando imports de core y llama attr/import para confirmar.
Salida: lista de OK/FAIL por símbolo. Exit code 1 si hay algún FAIL.
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
    Devuelve lista de (archivo, modulo_core, simbolo) para cada import de core.*
    Cubre:
      - from core.X import a, b, c   → (file, "core.X", "a"), ...
      - from core import X           → (file, "core", "X")  — se verificará como módulo
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
        fail(f"{file}: no se puede importar '{module}' — {e}")
        return False

    if symbol is None:
        ok(f"{file}: import {module}")
        return True

    if not hasattr(mod, symbol):
        # Puede ser un submódulo (ej: from core import quotes → core.quotes)
        try:
            importlib.import_module(f"{module}.{symbol}")
            ok(f"{file}: {module}.{symbol} (submódulo)")
            return True
        except ModuleNotFoundError:
            pass
        fail(f"{file}: '{module}' no tiene '{symbol}'")
        return False

    ok(f"{file}: {module}.{symbol}")
    return True


def scan_module_dot_attr(path: Path) -> list[tuple[str, str, str]]:
    """
    Detecta usos del patrón `alias.metodo(` donde alias fue importado
    como `from core import alias`. Ejemplo: `quotes.precio_actual(`.
    """
    results = []
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except SyntaxError:
        return results

    # Mapea alias → módulo core completo para imports tipo `from core import X`
    alias_to_module: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "core":
                for alias in node.names:
                    name = alias.asname or alias.name
                    alias_to_module[name] = f"core.{alias.name}"

    # Busca llamadas tipo alias.attr(...)
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
        print("No se encontraron imports de core/. Nada que verificar.")
        return 0

    # Deduplicar
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
        print(f"{RED}FAIL {failures} contrato(s) roto(s). Revisa core/ antes de continuar.{NC}")
    else:
        print(f"{GREEN}OK Todos los contratos UI<->core verificados.{NC}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
