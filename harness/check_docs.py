#!/usr/bin/env python3
"""
harness/check_docs.py - Chequeo determinista de documentacion.

Detecta simbolos publicos anadidos/eliminados en el diff de la sesion
(working tree + staged vs HEAD) en core/*.py y ui/common.py, y los cruza
contra las menciones en harness/docs/architecture.md, harness/docs/data-models.md
y CLAUDE.md, listando exactamente que falta o sobra. Un simbolo nuevo basta
con que este mencionado en UNO de los docs (el detalle vive en architecture.md
o data-models.md; CLAUDE.md se mantiene minimo); un simbolo eliminado no debe
seguir mencionado en NINGUNO.

Ademas, cruza la lista real de modulos del proyecto (core/*.py, ui/*.py,
ui/pages/*.py) contra README.md: cada modulo debe aparecer por nombre en la
seccion Estructura. Este cruce corre siempre que se invoca el script (no
depende del diff), para que el drift acumulado salga a la luz en la primera
sesion que toque codigo.

Es un check informativo: nunca debe lanzar una excepcion no controlada ni
bloquear close.sh por un fallo inesperado de git/IO (exit 0 en ese caso).
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


def simbolos_publicos(source: str) -> set[str]:
    """Simbolos publicos a nivel de modulo: def/async def, class y
    asignaciones a NOMBRE_EN_MAYUSCULAS (incluye AnnAssign). Excluye
    cualquier nombre que empiece por '_'. Devuelve set() si el source no
    parsea (SyntaxError)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    simbolos: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                simbolos.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    if target.id.isupper():
                        simbolos.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and not target.id.startswith("_"):
                if target.id.isupper():
                    simbolos.add(target.id)

    return simbolos


def menciona(doc_text: str, simbolo: str) -> bool:
    """True si doc_text menciona simbolo como palabra completa (\\b + re.escape)."""
    patron = r"\b" + re.escape(simbolo) + r"\b"
    return re.search(patron, doc_text) is not None


def modulos_del_proyecto() -> list[str]:
    """Rutas relativas (con /) de los modulos que README.md debe mencionar:
    core/*.py, ui/*.py y ui/pages/*.py, excluyendo privados (_*) y __init__."""
    rutas: list[str] = []
    for patron in ("core/*.py", "ui/*.py", "ui/pages/*.py"):
        for p in sorted(ROOT.glob(patron)):
            if p.name.startswith("_"):
                continue
            rutas.append(p.relative_to(ROOT).as_posix())
    return rutas


def modulos_sin_mencion_en_readme() -> list[str]:
    """Modulos del proyecto cuyo nombre de fichero no aparece en README.md."""
    if not README_MD.exists():
        return []
    texto = README_MD.read_text(encoding="utf-8")
    return [
        ruta
        for ruta in modulos_del_proyecto()
        if not menciona(texto, ruta.rsplit("/", 1)[-1])
    ]


def diff_simbolos(old_source: str, new_source: str) -> tuple[set[str], set[str]]:
    """Devuelve (anadidos, eliminados) entre old_source y new_source."""
    antes = simbolos_publicos(old_source)
    despues = simbolos_publicos(new_source)
    anadidos = despues - antes
    eliminados = antes - despues
    return anadidos, eliminados


def ficheros_cambiados() -> list[tuple[str, str]]:
    """Parsea `git status --porcelain -- core ui` y devuelve (status, ruta)
    solo para .py bajo core/ o exactamente ui/common.py."""
    resultado = subprocess.run(
        ["git", "status", "--porcelain", "--", "core", "ui"],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"git status fallo: {resultado.stderr.strip()}")

    cambiados: list[tuple[str, str]] = []
    for linea in resultado.stdout.splitlines():
        if not linea.strip():
            continue
        status = linea[:2]
        resto = linea[3:]

        if status.startswith("R"):
            # Formato: "old -> new"
            if " -> " in resto:
                ruta = resto.split(" -> ", 1)[1].strip()
            else:
                ruta = resto.strip()
        else:
            ruta = resto.strip()

        # Quita comillas si git citó la ruta (paths con espacios/unicode)
        if ruta.startswith('"') and ruta.endswith('"'):
            ruta = ruta[1:-1]

        es_core_py = ruta.startswith("core/") and ruta.endswith(".py")
        es_ui_common = ruta == "ui/common.py"
        if es_core_py or es_ui_common:
            cambiados.append((status.strip(), ruta))

    return cambiados


def contenido_head(ruta: str) -> str:
    """Devuelve el contenido de ruta en HEAD; '' si falla (fichero nuevo)."""
    resultado = subprocess.run(
        ["git", "show", f"HEAD:{ruta}"],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
    )
    if resultado.returncode != 0:
        return ""
    return resultado.stdout


def main() -> int:
    try:
        hallazgos: list[str] = []

        for ruta in modulos_sin_mencion_en_readme():
            hallazgos.append(
                f"{YELLOW}[WARN]{NC} README.md: modulo {ruta} sin mencion en la seccion Estructura"
            )

        cambiados = ficheros_cambiados()

        if not cambiados and not hallazgos:
            print(f"{GREEN}[OK]{NC} Sin cambios en core/ o ui/common.py - nada que cruzar; README.md cubre todos los modulos")
            return 0

        anadidos_por_fichero: dict[str, set[str]] = {}
        eliminados_por_fichero: dict[str, set[str]] = {}

        for status, ruta in cambiados:
            old_source = contenido_head(ruta)

            if status == "D":
                new_source = ""
            else:
                ruta_absoluta = ROOT / ruta
                if not ruta_absoluta.exists():
                    continue
                new_source = ruta_absoluta.read_text(encoding="utf-8")

            anadidos, eliminados = diff_simbolos(old_source, new_source)
            if anadidos:
                anadidos_por_fichero[ruta] = anadidos
            if eliminados:
                eliminados_por_fichero[ruta] = eliminados

        docs = {}
        for nombre, ruta_doc in DOCS:
            if ruta_doc.exists():
                docs[nombre] = ruta_doc.read_text(encoding="utf-8")
            else:
                docs[nombre] = ""
                print(f"{YELLOW}[WARN]{NC} No se encontro {ruta_doc.relative_to(ROOT)}, se trata como vacio")

        for ruta, simbolos in sorted(anadidos_por_fichero.items()):
            for simbolo in sorted(simbolos):
                if not any(menciona(texto, simbolo) for texto in docs.values()):
                    hallazgos.append(
                        f"{YELLOW}[WARN]{NC} {ruta}: simbolo nuevo '{simbolo}' sin mencion en ningun doc "
                        f"(documentalo en architecture.md o, si es de esquema JSON, en data-models.md)"
                    )

        for ruta, simbolos in sorted(eliminados_por_fichero.items()):
            for simbolo in sorted(simbolos):
                for nombre_doc, texto in docs.items():
                    if menciona(texto, simbolo):
                        hallazgos.append(
                            f"{YELLOW}[WARN]{NC} {ruta}: simbolo eliminado '{simbolo}' sigue mencionado en {nombre_doc}"
                        )

        if not hallazgos:
            print(f"{GREEN}[OK]{NC} Simbolos publicos del diff alineados con architecture.md / data-models.md / CLAUDE.md; README.md cubre todos los modulos")
            return 0

        for linea in hallazgos:
            print(linea)

        print()
        print(f"{RED}[FAIL]{NC} {len(hallazgos)} hallazgo(s) de documentacion pendientes de revisar.")
        return 1

    except Exception as e:  # noqa: BLE001 - check informativo, nunca debe romper close.sh
        print(f"[INFO] check_docs no pudo completarse: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
