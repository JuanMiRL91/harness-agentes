#!/usr/bin/env bash
# harness/close.sh — Session close protocol.
# Run when a feature is marked as "done" in feature_list.json.
# Usage: ./harness/close.sh  (from the project root)
#
# Steps:
#   1. Verifies that init.sh passes 100%
#   2. Reads the just-completed feature from progress/current.md
#   3. Detects changes in core/ or ui/ and warns if neither harness/docs/architecture.md
#      nor harness/docs/data-models.md were touched; also cross-checks the public
#      symbols of the diff against the docs (harness/check_docs.py, deterministic)
#   3b. If the commit is a fix (BUG_), reminds you of the systemic bug→check cycle
#   3c. Warns if CLAUDE.md exceeds 40,000 characters (it must stay minimal;
#      detail goes to architecture.md/data-models.md, changelog to history.md)
#   3d. Archives done/Cancelled features into harness/feature_list_archive.json
#      (the active file keeps only open tasks; global ids across both)
#   4. Moves progress/current.md to the end of progress/history.md and resets it
#   5. Makes the automatic commit with a conventional message
#
# Exit codes:
#   0 = session closed (commit made, or nothing to commit)
#   1 = error (init.sh red, or the feature in current.md is not "done")
#   3 = paused: docs pending or CLAUDE.md >40k — fix and re-run close.sh
#       (with non-interactive stdin, e.g. an agent, the pause is automatic)

set -euo pipefail

# Windows: when Python's stdout is NOT a real console (here, captured by bash
# `$(...)`), Python uses the system's ANSI code page codec (e.g. cp1252 on
# Spanish Windows) instead of UTF-8 — corrupting any non-ASCII character that
# the `"$PY" -c "..."` blocks of this script write to stdout for bash to
# collect (reproduced with the em-dash of the history.md header). Forcing
# UTF-8 here is a no-op on Linux/macOS (they already use UTF-8).
export PYTHONIOENCODING=utf-8

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()   { echo -e "${GREEN}[OK]${NC}   $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

# Detect Python executable (same as init.sh)
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
    PY="python3"
elif python -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
    PY="python"
else
    PY="python3"
fi

CURRENT="harness/progress/current.md"
HISTORY="harness/progress/history.md"
FEATURE_LIST="harness/feature_list.json"
FEATURE_ARCHIVE="harness/feature_list_archive.json"

echo "========================================"
echo "  $(basename "$ROOT") — close.sh"
echo "========================================"
echo ""

# ── 1. Green environment ─────────────────────────────────────────────────────
echo "▸ Verifying environment (harness/init.sh)..."
echo ""
if ! bash harness/init.sh; then
    echo ""
    fail "init.sh does not pass. Fix the errors before closing the session."
    exit 1
fi
echo ""

# ── 2. Detect completed feature ──────────────────────────────────────────────
echo "▸ Completed feature"

# Read from current.md (before resetting)
FEATURE_LINE=$(grep -m1 "Feature in progress" "$CURRENT" 2>/dev/null || true)
FEATURE_ID=""
FEATURE_NAME=""

if echo "$FEATURE_LINE" | grep -qE "#[0-9]+"; then
    FEATURE_ID=$(echo "$FEATURE_LINE" | grep -oE "#[0-9]+" | head -1 | tr -d '#')
    # Extract feature name from feature_list.json by id
    FEATURE_DATA=$("$PY" - <<PYEOF
import json, os
feat = None
for path in ("$FEATURE_LIST", "$FEATURE_ARCHIVE"):
    if not os.path.exists(path):
        continue
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    feat = next((x for x in data["features"] if str(x["id"]) == "$FEATURE_ID"), None)
    if feat:
        break
if feat:
    print(f"{feat['name']}|{feat['title']}|{feat['status']}")
PYEOF
)
    FEATURE_NAME=$(echo "$FEATURE_DATA" | cut -d'|' -f1)
    FEATURE_TITLE=$(echo "$FEATURE_DATA" | cut -d'|' -f2)
    FEATURE_STATUS=$(echo "$FEATURE_DATA" | cut -d'|' -f3)

    if [ "$FEATURE_STATUS" != "done" ]; then
        warn "Feature #$FEATURE_ID ($FEATURE_NAME) is not marked as 'done' in feature_list.json."
        warn "Mark it as done before closing the session."
        exit 1
    fi

    # Commit type: fix for bugs, feat for the rest
    if echo "$FEATURE_NAME" | grep -qi "^BUG_"; then
        COMMIT_TYPE="fix"
    else
        COMMIT_TYPE="feat"
    fi

    ok "Feature #$FEATURE_ID: $FEATURE_NAME — $FEATURE_TITLE"
else
    COMMIT_TYPE="chore"
    # No #id: use the "Feature in progress" text as the chore title (infrastructure
    # sessions without a backlog entry).
    CHORE_TITLE=$(echo "$FEATURE_LINE" | sed -E 's/.*Feature in progress:\*{0,2}//; s/<!--.*-->//; s/^[[:space:]_]+//; s/[[:space:]_]+$//')
    if [ -n "$CHORE_TITLE" ] && [ "$CHORE_TITLE" != "none" ]; then
        FEATURE_TITLE="$CHORE_TITLE"
        info "No feature id — committing as 'chore: ${CHORE_TITLE}'."
    else
        warn "No feature reference found in progress/current.md."
        info "The commit will use the generic message 'chore: session close'."
        FEATURE_TITLE="session close"
    fi
fi
echo ""

# ── 3. Do architecture.md / data-models.md need updating? ────────────────────
echo "▸ Checking documentation (harness/docs/architecture.md / data-models.md)"

# Modified code files (staged + unstaged)
CHANGED_CODE=$(git status --porcelain -- core/ ui/ 2>/dev/null | wc -l | tr -d ' ')

if [ "$CHANGED_CODE" -gt 0 ]; then
    info "There are $CHANGED_CODE modified file(s) in core/ or ui/."

    ARCH_CHANGED=$(git status --porcelain -- harness/docs/architecture.md 2>/dev/null | wc -l | tr -d ' ')
    DM_CHANGED=$(git status --porcelain -- harness/docs/data-models.md 2>/dev/null | wc -l | tr -d ' ')
    NEEDS_CONFIRM=0

    if [ "$ARCH_CHANGED" -eq 0 ] && [ "$DM_CHANGED" -eq 0 ]; then
        warn "Neither harness/docs/architecture.md nor data-models.md were modified — where is the change documented?"
        warn "Modules/functions/decisions → architecture.md · data schemas → data-models.md ·"
        warn "changelog → progress/current.md (this script archives it) · CLAUDE.md only if the one-line map changes."
        NEEDS_CONFIRM=1
    else
        [ "$ARCH_CHANGED" -gt 0 ] && ok "harness/docs/architecture.md updated"
        [ "$DM_CHANGED" -gt 0 ] && ok "harness/docs/data-models.md updated"
    fi

    # Deterministic cross-check: public symbols added/removed in the diff vs
    # mentions in architecture.md / data-models.md / CLAUDE.md (exact list,
    # not just "was the doc touched?") + coverage of all core/ and ui/ modules
    # in the Structure section of README.md
    if [ -f harness/check_docs.py ]; then
        if ! "$PY" harness/check_docs.py; then
            NEEDS_CONFIRM=1
        fi
    fi

    if [ "$NEEDS_CONFIRM" -eq 1 ]; then
        echo ""
        if [ -t 0 ]; then
            echo -e "${YELLOW}  Proceed anyway without updating the docs? [y/N]${NC} \c"
            read -r ANSWER || ANSWER=""
        else
            ANSWER="N"
            warn "non-interactive stdin — automatic pause (an agent cannot skip this warning)."
        fi
        if [[ ! "$ANSWER" =~ ^[yY]$ ]]; then
            warn "Session paused (exit 3). Update the docs and re-run ./harness/close.sh"
            exit 3
        fi
    fi
else
    ok "No changes in core/ or ui/ — docs need no update"
fi
echo ""

# ── 3b. Closed bug → systemic harness improvement ────────────────────────────
if [ "${COMMIT_TYPE:-}" = "fix" ]; then
    echo "▸ Systemic cycle (bug → harness check)"
    HARNESS_CHANGED=$(git status --porcelain -- harness/ .claude/ 2>/dev/null | wc -l | tr -d ' ')
    if [ "$HARNESS_CHANGED" -eq 0 ]; then
        warn "You are closing a BUG_ with no changes in harness/ or .claude/ — which check would have caught this bug earlier?"
        warn "If a reasonable one exists, add it (improve-harness skill) before closing; if not applicable, note it in current.md ('Systemic check: not applicable — reason')."
    else
        ok "The fix includes changes in harness/ or .claude/ (systemic cycle addressed)"
    fi
    echo ""
fi

# ── 3c. CLAUDE.md must stay minimal (≤40,000 characters) ─────────────────────
echo "▸ CLAUDE.md size"
CLAUDE_CHARS=$("$PY" -c "print(len(open('CLAUDE.md', encoding='utf-8').read()))" 2>/dev/null || echo 0)
if [ "$CLAUDE_CHARS" -gt 40000 ]; then
    warn "CLAUDE.md has $CLAUDE_CHARS characters (limit: 40000) — it is injected whole into every session."
    warn "Move the detail to harness/docs/architecture.md or data-models.md; the changelog goes to progress/history.md."
    if [ -t 0 ]; then
        echo -e "${YELLOW}  Proceed anyway with CLAUDE.md over the limit? [y/N]${NC} \c"
        read -r ANSWER_CLAUDE || ANSWER_CLAUDE=""
    else
        ANSWER_CLAUDE="N"
        warn "non-interactive stdin — automatic pause (an agent cannot skip this warning)."
    fi
    if [[ ! "$ANSWER_CLAUDE" =~ ^[yY]$ ]]; then
        warn "Session paused (exit 3). Reduce CLAUDE.md and re-run ./harness/close.sh"
        exit 3
    fi
else
    ok "CLAUDE.md within the limit ($CLAUDE_CHARS / 40000 characters)"
fi
echo ""

# ── 3d. Archive closed features ──────────────────────────────────────────────
echo "▸ Archiving closed features (done/Cancelled → feature_list_archive.json)"
ARCHIVED_N=$("$PY" - <<'PYEOF'
import json

ACTIVE = "harness/feature_list.json"
ARCHIVE = "harness/feature_list_archive.json"

with open(ACTIVE, encoding="utf-8") as f:
    active = json.load(f)

try:
    with open(ARCHIVE, encoding="utf-8") as f:
        archive = json.load(f)
except FileNotFoundError:
    archive = {
        "project": active.get("project", ""),
        "description": "Historical archive of closed features (done/Cancelled), "
                       "moved here by close.sh. Global ids with feature_list.json: "
                       "never reused or renumbered.",
        "rules": active.get("rules", {}),
        "features": [],
    }

closed = [f for f in active["features"] if f["status"] in ("done", "Cancelled")]
if closed:
    archive["features"].extend(closed)
    archive["features"].sort(key=lambda f: f["id"])
    active["features"] = [f for f in active["features"] if f["status"] not in ("done", "Cancelled")]
    for path, data in ((ACTIVE, active), (ARCHIVE, archive)):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
print(len(closed))
PYEOF
)
if [ "${ARCHIVED_N:-0}" -gt 0 ]; then
    ok "${ARCHIVED_N} feature(s) archived in harness/feature_list_archive.json"
else
    ok "Nothing to archive (no done/Cancelled in the active file)"
fi
echo ""

# ── 4. Update progress/ ──────────────────────────────────────────────────────
echo "▸ Updating progress/"

IS_TEMPLATE=$("$PY" -c "
import re, sys
content = open('$CURRENT', encoding='utf-8').read()
# Empty template = has the no-feature line and no real content in the Log
empty = ('_none_' in content) and ('- ...' in content)
print('1' if empty else '0')
")

if [ "$IS_TEMPLATE" = "0" ]; then
    TRANSFORMED=$("$PY" -c "
import re, sys
content = open('$CURRENT', encoding='utf-8').read()
content = re.sub(r'^> .*\n', '', content, flags=re.MULTILINE)
content = re.sub(r'\n{3,}', '\n\n', content)
date_m = re.search(r'\*\*Start:\*\*\s*(\d{4}-\d{2}-\d{2})', content)
date_str = date_m.group(1) if date_m else '????-??-??'
feat_line_m = re.search(r'\*\*Feature in progress:\*\*\s*(.+)', content)
header = None
if feat_line_m:
    val = re.sub(r'<!--.*?-->', '', feat_line_m.group(1)).strip()
    # Accepts '#N name', 'name (#N)', 'name [N]' — the order and the delimiter
    # have varied between sessions, so the id is searched at any position
    # instead of requiring it to come first.
    id_m = re.search(r'#(\d+)|\[(\d+)\]', val)
    if id_m and val != '_none_':
        fid = id_m.group(1) or id_m.group(2)
        name_part = (val[:id_m.start()] + val[id_m.end():]).strip(' ()[]' + chr(96) + ':')
        name_part = re.sub(r'^Feature\s+', '', name_part, flags=re.IGNORECASE).strip()
        if name_part:
            header = '## ' + date_str + ' — #' + fid + ' ' + name_part
if not header:
    header = '## ' + date_str + ' — Session closed'
content = re.sub(r'^# Current session.*', header, content, count=1, flags=re.MULTILINE)
sys.stdout.write(content)
")
    {
        echo ""
        echo "---"
        echo ""
        printf '%s\n' "$TRANSFORMED"
    } >> "$HISTORY"
    ok "Session appended to history.md"
else
    info "current.md is empty (template), not appended to history.md"
fi

cat > "$CURRENT" << 'TEMPLATE'
# Current session

> This file is emptied when each session closes and moved to `history.md`.
> While you work, **keep it updated in real time**, not at the end.

- **Feature in progress:** _none_  <!-- format: #N feature_name -->
- **Start:** _—_
- **Agent:** _—_

## Plan

_Describe in 3-5 bullets what you are going to do before touching code._

## Log

_Note here every significant step: files created, decisions, blockers._

- ...

## Next step

_If the session is interrupted, the first thing the next session must do._

---
TEMPLATE
ok "current.md reset to template"
echo ""

# ── 5. Automatic commit ──────────────────────────────────────────────────────
echo "▸ Automatic commit"

git add -A

if git diff --cached --quiet; then
    info "Nothing to commit — the working tree was already clean."
else
    if [ -n "$FEATURE_ID" ]; then
        COMMIT_MSG="${COMMIT_TYPE}(#${FEATURE_ID}): ${FEATURE_NAME} — ${FEATURE_TITLE}"
    else
        COMMIT_MSG="chore: ${FEATURE_TITLE}"
    fi

    git commit -m "$COMMIT_MSG"
    ok "Commit: $COMMIT_MSG"
fi

echo ""
echo "========================================"
echo -e "${GREEN}  ✓ Session closed successfully.${NC}"
echo "========================================"
