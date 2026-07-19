#!/usr/bin/env bash
# harness/init.sh — Verifies the environment before starting a work session.
# Usage: ./harness/init.sh  (from the project root)

set -euo pipefail

# Windows: when Python's stdout is not a real console (captured by bash `$(...)`
# or by a `pytest` pipe), Python may use the system's ANSI code page codec
# (e.g. cp1252) instead of UTF-8 — corrupting any non-ASCII character that a
# `"$PY" -c "..."` block writes to stdout (same fix as harness/close.sh).
# No-op on Linux/macOS.
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

# ── Detect Python executable ─────────────────────────────────────────────────
# On Windows Git Bash, 'python3' may point to the Microsoft Store stub.
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
    PY="python3"
elif python -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
    PY="python"
else
    PY="python3"  # fallback; section 1 will give the clear error
fi

echo "========================================"
echo "  $(basename "$ROOT") — init.sh"
echo "========================================"
echo ""

# ── 1. Python 3.9+ ───────────────────────────────────────────────────────────
echo "▸ Python environment"
if command -v "$PY" &>/dev/null && "$PY" -c "import sys; sys.exit(0)" 2>/dev/null; then
    PY_VER=$("$PY" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 9 ]; then
        ok "Python $PY_VER  ($PY)"
    else
        fail "Python $PY_VER — 3.9+ required"
    fi
else
    fail "Python 3.9+ not found (tried: python3, python)"
fi

# ── 2. Mandatory harness files ───────────────────────────────────────────────
echo ""
echo "▸ Harness files"
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
        fail "$f — not found"
    fi
done

# ── 3. Validate feature_list.json ────────────────────────────────────────────
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
        errors.append(f"Feature {feat['id']} '{feat['name']}': invalid status '{status}'")
    if status == "in_progress":
        in_progress.append(feat["name"])

for feat in archive_features:
    if feat.get("status") not in ("done", "Cancelled"):
        errors.append(
            f"Archive: feature {feat['id']} '{feat['name']}' with status "
            f"'{feat.get('status')}' — feature_list_archive.json may only contain done/Cancelled"
        )

ids = [f["id"] for f in data.get("features", [])] + [f["id"] for f in archive_features]
duplicates = sorted({i for i in ids if ids.count(i) > 1})
if duplicates:
    errors.append(f"duplicated ids between feature_list.json and feature_list_archive.json: {duplicates}")

if errors:
    for e in errors:
        print(f"\033[0;31m[FAIL]\033[0m   {e}")
    sys.exit(1)

if len(in_progress) > 1:
    print(f"\033[0;31m[FAIL]\033[0m   More than one feature in_progress: {in_progress}")
    sys.exit(1)
elif len(in_progress) == 1:
    print(f"\033[0;32m[OK]\033[0m   Feature in progress: {in_progress[0]}")
else:
    print(f"\033[0;32m[OK]\033[0m   No feature in progress (pick a pending one to start)")

done_total = len([f for f in data["features"] if f["status"] == "done"]) \
    + len([f for f in archive_features if f["status"] == "done"])
pending = [f["name"] for f in data["features"] if f["status"] == "pending"]
print(f"\033[0;32m[OK]\033[0m   {done_total} done (archive included) · {len(pending)} pending · {len(in_progress)} in_progress")
PYEOF
    [ $? -ne 0 ] && FAILED=1
fi

# ── 4. Python dependencies ───────────────────────────────────────────────────
echo ""
echo "▸ Dependencies"
if [ -f "harness/check_deps.py" ]; then
    "$PY" harness/check_deps.py
    [ $? -ne 0 ] && FAILED=1
else
    warn "harness/check_deps.py not found"
fi

# ── 5. Tests ─────────────────────────────────────────────────────────────────
echo ""
echo "▸ Tests"
TEST_COUNT=$( (find tests/ -name "test_*.py" 2>/dev/null || true) | wc -l | tr -d ' ')
if [ -d "tests" ] && [ "$TEST_COUNT" -gt 0 ]; then
    if "$PY" -m pytest --version &>/dev/null 2>&1; then
        if "$PY" -m pytest tests/ -q --tb=short 2>&1; then
            ok "All tests pass (pytest, alphabetical order)"
            # A test file can leave contaminated shared state (mocks/modules in
            # sys.modules) that only breaks ANOTHER file depending on execution
            # order. Re-running in reverse alphabetical order is cheap (same
            # runtime) and exposes exactly that class of leak without depending
            # on a random-order plugin.
            REVERSE_FILES=$(find tests/ -name "test_*.py" 2>/dev/null | sort -r)
            if "$PY" -m pytest $REVERSE_FILES -q --tb=short 2>&1; then
                ok "All tests pass (pytest, reverse order — isolation between files)"
            else
                fail "Tests fail in reverse order — there is shared state between test files"
            fi
        else
            fail "There are failing tests — review before continuing"
        fi
    else
        if "$PY" -m unittest discover -s tests/ -q 2>&1; then
            ok "All tests pass (unittest)"
        else
            fail "There are failing tests — review before continuing"
        fi
    fi
else
    warn "No tests yet — add tests before closing the next feature"
fi

# ── 6. UI↔core contracts ─────────────────────────────────────────────────────
echo ""
echo "▸ UI↔core contracts"
if [ -f "harness/check_contracts.py" ]; then
    if "$PY" harness/check_contracts.py 2>&1; then
        : # the script already prints ok
    else
        fail "There are broken contracts between ui/ and core/ — the app will fail at runtime"
    fi
else
    warn "harness/check_contracts.py not found"
fi

# ── 7. Placeholder text in literals ──────────────────────────────────────────
echo ""
echo "▸ Placeholder text (core/ and ui/)"
if [ -f "harness/check_placeholder.py" ]; then
    if "$PY" harness/check_placeholder.py 2>&1; then
        : # the script already prints ok
    else
        fail "There is placeholder/erroneous text in core/ or ui/ string literals"
    fi
else
    warn "harness/check_placeholder.py not found"
fi

# ── Final result ─────────────────────────────────────────────────────────────
echo ""
echo "========================================"
if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}  ✓ Environment ready. You can start working.${NC}"
else
    echo -e "${RED}  ✗ There are errors. Fix them before continuing.${NC}"
fi
echo "========================================"

exit "$FAILED"
