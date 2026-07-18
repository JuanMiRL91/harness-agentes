#!/usr/bin/env python3
"""
harness/check_deps.py — Detecta imports de terceros no declarados en requirements.txt
y los añade automáticamente con la versión instalada.

También verifica que los paquetes declarados en requirements.txt estén instalados.
Exit code siempre 0 — emite WARN pero no bloquea el harness.
"""

import ast
import importlib.metadata
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCAN_DIRS = ["core", "ui", "tests", "scripts"]

# import_name → PyPI package name cuando difieren
IMPORT_TO_PKG = {
    "dotenv":      "python-dotenv",
    "PIL":         "Pillow",
    "cv2":         "opencv-python",
    "yaml":        "PyYAML",
    "sklearn":     "scikit-learn",
    "bs4":         "beautifulsoup4",
    "dateutil":    "python-dateutil",
    "attr":        "attrs",
    "pkg_resources": "setuptools",
}

# Imports internos que nunca deben buscarse como paquete
_SKIP = {"__future__", ""}

GREEN  = "\033[0;32m"
YELLOW = "\033[1;33m"
NC     = "\033[0m"

ok   = lambda m: print(f"{GREEN}[OK]{NC}   {m}")
warn = lambda m: print(f"{YELLOW}[WARN]{NC} {m}")


# ── Utilidades ────────────────────────────────────────────────────────────────

def _stdlib_names():
    if hasattr(sys, "stdlib_module_names"):           # Python 3.10+
        return sys.stdlib_module_names
    # Fallback Python 3.9 — lista comprehensiva
    return {
        "abc", "ast", "asyncio", "builtins", "cmath", "cmd", "code",
        "collections", "concurrent", "contextlib", "copy", "csv",
        "dataclasses", "datetime", "decimal", "difflib", "dis", "email",
        "encodings", "enum", "errno", "fileinput", "fnmatch", "fractions",
        "ftplib", "functools", "gc", "getopt", "getpass", "gettext",
        "glob", "gzip", "hashlib", "heapq", "hmac", "html", "http",
        "idlelib", "imaplib", "importlib", "inspect", "io", "ipaddress",
        "itertools", "json", "keyword", "lib2to3", "linecache", "locale",
        "logging", "mailbox", "math", "mimetypes", "mmap", "multiprocessing",
        "netrc", "numbers", "operator", "os", "pathlib", "pickle",
        "pickletools", "pkgutil", "platform", "pprint", "profile", "pstats",
        "pty", "pwd", "py_compile", "pyclbr", "pydoc", "queue", "random",
        "re", "readline", "reprlib", "rlcompleter", "runpy", "sched",
        "secrets", "select", "shelve", "shlex", "shutil", "signal",
        "site", "smtplib", "socket", "socketserver", "sqlite3", "ssl",
        "stat", "statistics", "string", "struct", "subprocess", "sys",
        "sysconfig", "tabnanny", "tarfile", "tempfile", "textwrap",
        "threading", "time", "timeit", "tkinter", "token", "tokenize",
        "tomllib", "traceback", "tracemalloc", "typing", "types",
        "unicodedata", "unittest", "urllib", "uuid", "venv", "warnings",
        "weakref", "winreg", "winsound", "wsgiref", "xml", "xmlrpc",
        "zipfile", "zipimport", "zlib", "zoneinfo", "configparser",
        "copyreg", "curses", "dbm", "formatter", "grp", "imghdr",
        "mailbox", "nis", "nntplib", "optparse", "ossaudiodev",
        "pipes", "poplib", "posix", "posixpath", "quopri",
        "rlcompleter", "sndhdr", "spwd", "sunau", "symtable",
        "syslog", "telnetlib", "termios", "test", "tty", "turtle",
        "turtledemo", "uu", "wave", "xdrlib", "xxlimited",
    }


def _local_packages():
    # "harness" no esta en SCAN_DIRS (no se escanea) pero SI es un paquete local:
    # los tests importan harness.check_docs y no debe acabar en requirements.txt
    local = set(SCAN_DIRS) | {"harness"}
    for f in ROOT.glob("*.py"):
        local.add(f.stem)
    return local


def _extract_imports(path):
    """Devuelve el conjunto de nombres de módulo de nivel superior importados en un .py."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _parse_requirements():
    """Devuelve {nombre_normalizado: línea_original} de requirements.txt."""
    req_file = ROOT / "requirements.txt"
    if not req_file.exists():
        return {}
    pkgs = {}
    for line in req_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[>=<!;#\[ \t]", line)[0].strip()
        if name:
            pkgs[_norm(name)] = line
    return pkgs


def _norm(name):
    """Normaliza nombre de paquete: minúsculas, guiones = guiones bajos."""
    return name.lower().replace("-", "_")


def _packages_distributions():
    """Devuelve {nombre_módulo: [nombre_paquete]} para los paquetes instalados."""
    try:
        return importlib.metadata.packages_distributions()      # Python 3.11+
    except AttributeError:
        pass
    mapping = {}
    for dist in importlib.metadata.distributions():
        pkg_name = dist.metadata.get("Name") or ""
        top = dist.read_text("top_level.txt") or ""
        for mod in top.strip().splitlines():
            mod = mod.strip()
            if mod:
                mapping.setdefault(mod, []).append(pkg_name)
    return mapping


def _pkg_for_import(imp, pkg_dist):
    """
    Devuelve el nombre PyPI del paquete que provee `imp`.
    Orden: mapeo manual → pkg_dist → asume nombre == import (funciona para
    plotly, pandas, streamlit, yfinance, openpyxl, requests, pytest…).
    """
    if imp in IMPORT_TO_PKG:
        return IMPORT_TO_PKG[imp]
    if imp in pkg_dist:
        return pkg_dist[imp][0]
    # Último recurso: muchos paquetes tienen import_name == package_name
    return imp


def _installed_version(pkg_name):
    try:
        return importlib.metadata.version(pkg_name)
    except importlib.metadata.PackageNotFoundError:
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    stdlib     = _stdlib_names()
    local      = _local_packages()
    reqs       = _parse_requirements()
    pkg_dist   = _packages_distributions()

    # 1. Recopilar todos los imports del proyecto
    all_imports = set()
    for scan_dir in SCAN_DIRS:
        d = ROOT / scan_dir
        if d.exists():
            for f in d.rglob("*.py"):
                all_imports.update(_extract_imports(f))

    # 2. Filtrar: solo terceros (no stdlib, no locales, no internos)
    third_party = all_imports - stdlib - local - _SKIP

    # 3. Detectar los que no están en requirements.txt
    missing = []
    for imp in sorted(third_party):
        pkg = _pkg_for_import(imp, pkg_dist)
        if _norm(pkg) not in reqs:
            missing.append((imp, pkg))

    # 4. Añadir los que faltan a requirements.txt
    if missing:
        req_file = ROOT / "requirements.txt"
        content  = req_file.read_text(encoding="utf-8") if req_file.exists() else ""
        if content and not content.endswith("\n"):
            content += "\n"
        added = []
        for imp, pkg in missing:
            ver = _installed_version(pkg)
            if ver:
                major_minor = ".".join(ver.split(".")[:2])
                line = f"{pkg}>={major_minor}"
            else:
                line = pkg
            content += line + "\n"
            added.append((imp, pkg, line))
        req_file.write_text(content, encoding="utf-8")
        for imp, pkg, line in added:
            warn(f"Añadido a requirements.txt: {line}  (import '{imp}')")
        warn("Revisa las versiones añadidas y ejecuta: pip install -r requirements.txt")
    else:
        ok("requirements.txt cubre todas las dependencias detectadas")

    # 5. Verificar que lo declarado en requirements.txt esté instalado
    not_installed = []
    for norm_name, orig_line in reqs.items():
        orig_pkg = re.split(r"[>=<!;#\[ \t]", orig_line)[0].strip()
        if _installed_version(orig_pkg) is None:
            not_installed.append(orig_pkg)

    if not_installed:
        warn(f"No instalados: {', '.join(not_installed)}")
        warn("Ejecuta: pip install -r requirements.txt")
    elif not missing:
        ok("Todos los paquetes de requirements.txt están instalados")

    return 0


if __name__ == "__main__":
    sys.exit(main())
