#!/usr/bin/env bash
# harness/init.sh — Verifica el entorno antes de iniciar una sesión de trabajo.
# Uso: ./harness/init.sh  (desde la raíz del proyecto)

set -euo pipefail

# Windows: cuando stdout de Python no es una consola real (capturado por
# `$(...)` de bash o por un pipe de `pytest`), Python puede usar el códec de
# la página de códigos ANSI del sistema (p.ej. cp1252) en vez de UTF-8 —
# corrompe cualquier tilde que un bloque `"$PY" -c "..."` escriba a stdout
# (mismo fix que harness/close.sh). No-op en Linux/macOS.
export PYTHONIOENCODING=utf-8

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC}   $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; FAILED=1; }

FAILED=0

# ── Detectar ejecutable Python ────────────────────────────────────────────────
# En Windows Git Bash, 'python3' puede apuntar al stub de Microsoft Store.
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
    PY="python3"
elif python -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
    PY="python"
else
    PY="python3"  # fallback; la sección 1 dará el error claro
fi

echo "========================================"
echo "  $(basename "$ROOT") — init.sh"
echo "========================================"
echo ""

# ── 1. Python 3.9+ ───────────────────────────────────────────────────────────
echo "▸ Entorno Python"
if command -v "$PY" &>/dev/null && "$PY" -c "import sys; sys.exit(0)" 2>/dev/null; then
    PY_VER=$("$PY" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 9 ]; then
        ok "Python $PY_VER  ($PY)"
    else
        fail "Python $PY_VER — se requiere 3.9+"
    fi
else
    fail "Python 3.9+ no encontrado (probado: python3, python)"
fi

# ── 2. Archivos obligatorios del harness ─────────────────────────────────────
echo ""
echo "▸ Archivos del harness"
REQUIRED_FILES=(
    "AGENTS.md"
    "harness/CHECKPOINTS.md"
    "harness/feature_list.json"
    "harness/feature_list_archive.json"
    "harness/progress/current.md"
    "harness/progress/history.md"
    "harness/docs/architecture.md"
    "harness/docs/conventions.md"
    "harness/docs/verification.md"
)
for f in "${REQUIRED_FILES[@]}"; do
    if [ -f "$f" ]; then
        ok "$f"
    else
        fail "$f — no encontrado"
    fi
done

# ── 3. Validar feature_list.json ─────────────────────────────────────────────
echo ""
echo "▸ harness/feature_list.json (+ feature_list_archive.json)"
if [ -f "harness/feature_list.json" ]; then
    "$PY" - <<'PYEOF'
import json, sys

with open("harness/feature_list.json", encoding="utf-8") as f:
    data = json.load(f)
try:
    with open("harness/feature_list_archive.json", encoding="utf-8") as f:
        archive_features = json.load(f).get("features", [])
except FileNotFoundError:
    archive_features = []

valid_statuses = {"pending", "in_progress", "done", "blocked", "Postponed", "Cancelled"}
in_progress = []
errors = []

for feat in data.get("features", []):
    status = feat.get("status", "")
    if status not in valid_statuses:
        errors.append(f"Feature {feat['id']} '{feat['name']}': status '{status}' no válido")
    if status == "in_progress":
        in_progress.append(feat["name"])

for feat in archive_features:
    if feat.get("status") not in ("done", "Cancelled"):
        errors.append(
            f"Archivo: feature {feat['id']} '{feat['name']}' con status "
            f"'{feat.get('status')}' — en feature_list_archive.json solo puede haber done/Cancelled"
        )

ids = [f["id"] for f in data.get("features", [])] + [f["id"] for f in archive_features]
duplicados = sorted({i for i in ids if ids.count(i) > 1})
if duplicados:
    errors.append(f"ids duplicados entre feature_list.json y feature_list_archive.json: {duplicados}")

if errors:
    for e in errors:
        print(f"\033[0;31m[FAIL]\033[0m   {e}")
    sys.exit(1)

if len(in_progress) > 1:
    print(f"\033[0;31m[FAIL]\033[0m   Más de una feature in_progress: {in_progress}")
    sys.exit(1)
elif len(in_progress) == 1:
    print(f"\033[0;32m[OK]\033[0m   Feature en curso: {in_progress[0]}")
else:
    print(f"\033[0;32m[OK]\033[0m   Sin features en curso (elige una pending para empezar)")

done_total = len([f for f in data["features"] if f["status"] == "done"]) \
    + len([f for f in archive_features if f["status"] == "done"])
pending = [f["name"] for f in data["features"] if f["status"] == "pending"]
print(f"\033[0;32m[OK]\033[0m   {done_total} done (archivo incluido) · {len(pending)} pending · {len(in_progress)} in_progress")
PYEOF
    [ $? -ne 0 ] && FAILED=1
fi

# ── 4. Dependencias Python ────────────────────────────────────────────────────
echo ""
echo "▸ Dependencias"
if [ -f "harness/check_deps.py" ]; then
    "$PY" harness/check_deps.py
    [ $? -ne 0 ] && FAILED=1
else
    warn "harness/check_deps.py no encontrado"
fi

# ── 5. Tests ──────────────────────────────────────────────────────────────────
echo ""
echo "▸ Tests"
TEST_COUNT=$( (find tests/ -name "test_*.py" 2>/dev/null || true) | wc -l | tr -d ' ')
if [ -d "tests" ] && [ "$TEST_COUNT" -gt 0 ]; then
    if "$PY" -m pytest --version &>/dev/null 2>&1; then
        if "$PY" -m pytest tests/ -q --tb=short 2>&1; then
            ok "Todos los tests pasan (pytest, orden alfabético)"
            # Un fichero de test puede
            # dejar estado compartido (mocks/módulos en sys.modules) contaminado que
            # solo rompe OTRO fichero según el orden de ejecución. Re-ejecutar en
            # orden alfabético inverso es barato (mismo runtime) y expone justo esa
            # clase de fuga sin depender de un plugin de orden aleatorio.
            REVERSE_FILES=$(find tests/ -name "test_*.py" 2>/dev/null | sort -r)
            if "$PY" -m pytest $REVERSE_FILES -q --tb=short 2>&1; then
                ok "Todos los tests pasan (pytest, orden inverso — aislamiento entre ficheros)"
            else
                fail "Tests fallan en orden inverso — hay estado compartido entre ficheros de test"
            fi
        else
            fail "Hay tests fallando — revisa antes de continuar"
        fi
    else
        if "$PY" -m unittest discover -s tests/ -q 2>&1; then
            ok "Todos los tests pasan (unittest)"
        else
            fail "Hay tests fallando — revisa antes de continuar"
        fi
    fi
else
    warn "No hay tests todavía — añade tests antes de cerrar la próxima feature"
fi

# ── 6. Contratos UI↔core ─────────────────────────────────────────────────────
echo ""
echo "▸ Contratos UI↔core"
if [ -f "harness/check_contracts.py" ]; then
    if "$PY" harness/check_contracts.py 2>&1; then
        : # ok ya lo imprime el script
    else
        fail "Hay contratos rotos entre ui/ y core/ — la app fallará en runtime"
    fi
else
    warn "harness/check_contracts.py no encontrado"
fi

# ── 7. Texto placeholder en literales ─────────────────────────────────────────
echo ""
echo "▸ Texto placeholder (core/ y ui/)"
if [ -f "harness/check_placeholder.py" ]; then
    if "$PY" harness/check_placeholder.py 2>&1; then
        : # ok ya lo imprime el script
    else
        fail "Hay texto placeholder/erróneo en cadenas de core/ o ui/ (bug #128)"
    fi
else
    warn "harness/check_placeholder.py no encontrado"
fi

# ── Resultado final ───────────────────────────────────────────────────────────
echo ""
echo "========================================"
if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}  ✓ Entorno listo. Puedes empezar a trabajar.${NC}"
else
    echo -e "${RED}  ✗ Hay errores. Resuélvelos antes de continuar.${NC}"
fi
echo "========================================"

exit "$FAILED"
