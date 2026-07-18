#!/usr/bin/env python3
"""Detecta texto placeholder/erroneo conocido en literales de cadena de core/ y ui/.

Origen tipico: texto de relleno que llega a produccion sin que nadie lo
detecte. Este check recorre por AST los literales de cadena (incluidas f-strings)
de core/ y ui/ y falla si contienen algun termino de la lista negra.

Solo stdlib. Exit 0 si limpio, 1 si hay hallazgos.
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

GREEN = "\033[0;32m"
RED = "\033[0;31m"
NC = "\033[0m"

# Terminos que nunca deben aparecer en una cadena de produccion.
# (termino, case_sensitive)
FORBIDDEN = [
    ("lorem ipsum", False),     # texto de relleno clasico
    ("TODO:", True),            # marcador pendiente dentro de un literal visible
    ("FIXME", True),
]

SCAN_DIRS = ["core", "ui"]


def _strings_de(tree: ast.AST):
    """Genera (lineno, valor) de cada literal str del arbol, f-strings incluidas."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


def main() -> int:
    hallazgos = []
    for d in SCAN_DIRS:
        for py in sorted((ROOT / d).rglob("*.py")):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"))
            except SyntaxError as e:
                hallazgos.append((py, e.lineno or 0, f"SyntaxError: {e.msg}"))
                continue
            for lineno, valor in _strings_de(tree):
                for termino, case_sensitive in FORBIDDEN:
                    pajar = valor if case_sensitive else valor.lower()
                    aguja = termino if case_sensitive else termino.lower()
                    if aguja in pajar:
                        hallazgos.append((py, lineno, f"contiene '{termino}'"))

    if hallazgos:
        for py, lineno, motivo in hallazgos:
            rel = py.relative_to(ROOT)
            print(f"{RED}[FAIL]{NC}   {rel}:{lineno} — {motivo}")
        print(f"{RED}[FAIL]{NC}   {len(hallazgos)} literal(es) con texto placeholder/erroneo")
        return 1

    print(f"{GREEN}[OK]{NC}   Sin texto placeholder en literales de core/ y ui/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
