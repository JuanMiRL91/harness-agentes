#!/usr/bin/env bash
# harness/close.sh — Session close protocol.
# Run when a feature is marked as "done" in feature_list.json.
# Usage: ./harness/close.sh  (from the project root)
#
# Steps (any check that can `exit` runs BEFORE the archiving in 3c):
#   1. init.sh passes 100%
#   2. Reads the completed task from progress/current.md (`#N` or `[N]` marker)
#   2b. If the active backlog has `done` tasks, current.md must narrate them
#       (harness/check_session_log.py)
#   3a. Size gates: CLAUDE.md <= 15,000 chars, architecture.md <= 60,000 chars
#   3b. Comment gate on the changed files (harness/check_comments.py --working)
#   3c. Archives done/Cancelled tasks into harness/feature_list_archive.json
#   4. Appends current.md to history.md, resets it and rotates history.md by size
#   5. Automatic conventional commit
#
# Takes 1-2 min and is NOT reentrant: one run, in the foreground, nothing in parallel.
#
# Exit codes:
#   0 = session closed (commit made, or nothing to commit)
#   1 = error (init.sh red, or the task in current.md is not "done")
#   3 = paused: session log missing, comments or a doc over its size limit — fix
#       and re-run close.sh (with non-interactive stdin, e.g. an agent, the pause
#       is automatic)

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

if echo "$FEATURE_LINE" | grep -qE "#[0-9]+|\[[0-9]+\]"; then
    FEATURE_ID=$(echo "$FEATURE_LINE" | grep -oE "#[0-9]+|\[[0-9]+\]" | head -1 | tr -d '#[]')
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
    # Drops the template's `_none_` placeholder even with text after it; inner `_` are kept.
    CHORE_TITLE=$(echo "$FEATURE_LINE" | sed -E 's/.*Feature in progress:\*{0,2}//; s/<!--.*-->//; s/^[[:space:]]*[_*]+[nN]one[_*]+[[:space:]]*(—|–|-|:)?[[:space:]]*//; s/^[[:space:]_*]+//; s/[[:space:]_*]+$//')
    if echo "$CHORE_TITLE" | grep -q '[[:alnum:]]'; then
        FEATURE_TITLE="$CHORE_TITLE"
        info "No feature id — committing as 'chore: ${CHORE_TITLE}'."
    else
        warn "No feature reference found in progress/current.md."
        info "The commit will use the generic message 'chore: session close'."
        FEATURE_TITLE="session close"
    fi
fi
echo ""

# ── 2b. Session log required when there are done tasks ───────────────────────
echo "▸ Session log (current.md vs done tasks)"
if ! "$PY" harness/check_session_log.py; then
    echo ""
    warn "Session paused (exit 3). Write the log and re-run ./harness/close.sh"
    exit 3
fi
echo ""

# ── 3a. Size gates (injected or read every session) ──────────────────────────
size_gate() {  # file, limit, hint
    local chars answer
    chars=$("$PY" -c "print(len(open('$1', encoding='utf-8').read()))" 2>/dev/null || echo 0)
    if [ "$chars" -le "$2" ]; then
        ok "$1 within the limit ($chars / $2 characters)"
        return
    fi
    warn "$1 has $chars characters (limit: $2). $3"
    if [ -t 0 ]; then
        echo -e "${YELLOW}  Proceed anyway with $1 over the limit? [y/N]${NC} \c"
        read -r answer || answer=""
    else
        answer="N"
        warn "non-interactive stdin — automatic pause (an agent cannot skip this warning)."
    fi
    if [[ ! "$answer" =~ ^[yY]$ ]]; then
        warn "Session paused (exit 3). Trim $1 and re-run ./harness/close.sh"
        exit 3
    fi
}
echo "▸ Doc sizes"
size_gate CLAUDE.md 15000 "It is injected whole into every session: decisions, paths and rules only."
size_gate harness/docs/architecture.md 60000 "Keep decisions, invariants and verified findings; delete what the code already says."
echo ""

# ── 3b. Comment gate (same rule as the pre-commit hook) ──────────────────────
# Checked here, before archiving: if the hook rejected the commit of §5, current.md and
# the done tasks would already be archived.
echo "▸ Comments in the changed files"
if ! "$PY" harness/check_comments.py --working; then
    warn "Session paused (exit 3). Trim the flagged comments and re-run ./harness/close.sh"
    exit 3
fi
echo ""

# ── 3c. Archive closed features ──────────────────────────────────────────────
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
# Same per-line rule as check_session_log.is_template(): placeholder line AND empty log bullet.
lines = content.splitlines()
placeholder = any(l.startswith('- **Feature in progress:**') and '_none_' in l for l in lines)
empty_log = any(l.strip() == '- ...' for l in lines)
print('1' if (placeholder and empty_log) else '0')
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
        own = re.sub(r'^[\\s]*[_*]+[nN]one[_*]+[\\s]*[—–:-]?\\s*', '', val).strip(' _*')
        if re.search(r'[^\\W_]', own):
            header = '## ' + date_str + ' — ' + own
if not header:
    header = '## ' + date_str + ' — Session closed'
# Without the template H1 the entry would end up glued to the previous one: prepend the header.
content, n_sub = re.subn(r'^# Current session.*', header, content, count=1, flags=re.MULTILINE)
if not n_sub:
    content = header + '\\n\\n' + content.lstrip()
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

"$PY" harness/rotate_history.py || warn "rotate_history.py failed (does not block the close)"

cat > "$CURRENT" << 'TEMPLATE'
# Current session

> Emptied on close and moved to `history.md`. Brief: what, decisions, blockers.

- **Feature in progress:** _none_  <!-- format: #N feature_name -->
- **Start:** _—_

## Log

- ...

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
