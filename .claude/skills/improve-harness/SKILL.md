---
name: improve-harness
description: Improve or extend the project's development harness. Use it when the user asks to add verifications to init.sh/close.sh, improve existing checks, add new scripts to the harness, or any change in the development infrastructure (not in the app itself).
---

# Improving the harness

The harness is the project's **development infrastructure**. It is not part of the app.

## Harness map

| File | What it does | When to modify |
|---------|----------|-----------------|
| `harness/init.sh` | Pre-work verification: Python ≥3.9, mandatory files, feature_list.json, dependencies (`check_deps.py`), tests, UI↔core contracts (`check_contracts.py`) | To add/modify checks that must pass before working |
| `harness/close.sh` | Session close: calls init.sh, detects outdated docs (architecture.md/data-models.md + `check_docs.py`), warns if CLAUDE.md exceeds 40k characters, reminds the systemic bug→check cycle on `fix` commits, archives done/Cancelled features → feature_list_archive.json, archives current.md→history.md, makes the automatic commit. Exit: 0 closed · 1 error · 3 paused (non-interactive stdin = automatic pause) | To modify the close flow |
| `harness/check_contracts.py` | Verifies that all `ui/→core/` imports point to real symbols | To add new contract types |
| `harness/check_docs.py` | Deterministic docs cross-check: public symbols added/removed in the session diff (`core/*.py`, `ui/common.py` vs HEAD, via AST) vs mentions in `architecture.md`/`data-models.md`/`CLAUDE.md` (new symbol: a mention in ONE is enough; removed: it must remain in none) + module coverage in README.md (every `core/*.py`, `ui/*.py`, `ui/pages/*.py` must appear by name in the Structure section; runs always, does not depend on the diff); exit 1 is informative (it only triggers close.sh's confirmation) | To extend which files or docs are cross-checked |
| `harness/check_deps.py` | Detects third-party imports not declared in `requirements.txt` and adds them automatically | To extend dependency detection |
| `harness/feature_list.json` | ACTIVE backlog of features and bugs (pending/in_progress/blocked) | Only via `/add-feature` and `/add-bug`, never directly |
| `harness/feature_list_archive.json` | Archive of closed features (done/Cancelled), global ids with the active file | Only written by close.sh (step 3d) and the viewer when reactivating an entry |
| `harness/viewer.py` | Streamlit viewer of the backlog (single active+archive view; changing a status routes each feature to its file) | To improve progress visualization |
| `harness/progress/current.md` | Active session state (close.sh reads and archives it) | Updated during the work session |
| `harness/progress/history.md` | Append-only historical log | Only written via close.sh |
| `harness/docs/` | architecture.md (fine detail of modules/decisions), data-models.md (data schemas), conventions.md, verification.md | To update technical documentation |
| `harness/CHECKPOINTS.md` | Objective criteria for a correct final state | To add new evaluation points |
| `AGENTS.md` (root) | The contract the agent reads: how to pick a task (§4, `BUG_` bugs first), hard rules, lifecycle with init.sh/close.sh | If the change alters the agent's flow (priorities, states, session steps), keep it in sync |
| `.claude/settings.json` | Versioned Claude Code permissions: allow (init/close/pytest/read-only git) + deny (Edit/Write of docs/IDEAS.md and history.md) | To tighten/relax permissions on every machine |
| `.claude/agents/implementer.md` | Native subagent that implements ONE backlog task (full protocol; launched by orchestrate-backlog with haiku/sonnet/opus) | If the subagent's per-task protocol changes |

## Windows/Linux compatibility

The bash scripts use `$PY` (not `python3` directly). Both `init.sh` and `close.sh`
detect the correct executable at start:

```bash
# At the start of init.sh and close.sh — on Windows Git Bash, python3 may be the Microsoft Store stub
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
    PY="python3"
elif python -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)" 2>/dev/null; then
    PY="python"
else
    PY="python3"  # fallback; section 1 will give the clear error
fi
```

Every Python use in the scripts goes through `"$PY"`, never `python3` directly.

The harness Python scripts (`check_deps.py`, `check_contracts.py`) can have encoding
problems on Windows (cp1252 does not support characters like `✓`, `✗`, `↔`). Use
ASCII only in these scripts' output messages.

## init.sh structure

Numbered sections. Pattern of each section:
```bash
# ── N. Description ───────────────────────────────────────────────────────────
echo ""
echo "▸ Description"
# ... checks ...
[ $? -ne 0 ] && FAILED=1
```

Current sections:
1. Python 3.9+ (with `$PY` detection)
2. Mandatory harness files
3. Validate feature_list.json
4. Dependencies (via `$PY harness/check_deps.py`)
5. Tests (`$PY -m pytest` with unittest fallback)
6. UI↔core contracts (via `$PY harness/check_contracts.py`)

To add a section: insert it before the "Final result" block with the next number.

**Severity rule**: `fail()` increments `$FAILED` and blocks the start. `warn()` only
informs. Use `warn()` for recoverable issues (deps not installed, docs not updated).
Use `fail()` for issues that will prevent work (Python not found, failing tests,
broken contracts).

## check_deps.py — how it works

1. Scans AST imports of `core/`, `ui/`, `tests/`
2. Filters stdlib (`sys.stdlib_module_names` on 3.10+, static list on 3.9) and local
   modules (`core`, `ui`, `tests`, `.py` files at root)
3. Resolves import→package via `IMPORT_TO_PKG` (manual mapping for differing cases)
   → `packages_distributions()` → fallback to the import's own name
4. If the package is not in `requirements.txt` → adds it with `pkg>=major.minor`
   (installed version) or without version if not installed
5. Verifies that what requirements.txt declares is installed → WARN if not
6. Exit code always 0 (it never blocks the harness)

To extend the import→package mapping: add entries to `IMPORT_TO_PKG` in `check_deps.py`:
```python
IMPORT_TO_PKG = {
    "dotenv":   "python-dotenv",
    "PIL":      "Pillow",
    # add new cases here
}
```

## close.sh structure

Fixed steps (do not reorder):
1. Verifies that init.sh passes 100%
2. Reads the completed feature from current.md (looks for `#N` in the "Feature in
   progress" line; the entry is searched in feature_list.json AND
   feature_list_archive.json). Without `#N`, that line's text is used as the
   `chore:` commit title
3. Detects changes in `core/` or `ui/` and warns if neither
   harness/docs/architecture.md nor harness/docs/data-models.md were touched
   (3c: additionally warns if CLAUDE.md exceeds 40k characters). Pauses end with
   **exit 3**; with non-interactive stdin the pause is automatic, no question asked
3d. Archives done/Cancelled features into feature_list_archive.json (sorted by id;
   creates the file if it does not exist)
4. Archives current.md → history.md and resets current.md to the template
5. `git add -A` + commit with a conventional message

Commit type: `fix` for names starting with `BUG_`, `feat` for the rest.
Message: `fix(#N): name — title` or `feat(#N): name — title`.

To add new logic: inside an existing step, or as a new step between 3 and 4.

## Harness script conventions

- **Harness Python** (check_deps.py, check_contracts.py, etc.):
  - No external dependencies — stdlib only + project modules via
    `sys.path.insert(0, str(ROOT))`. Exception: `viewer.py` (uses Streamlit) — it is
    a visualization app, not a check that must run in any environment.
  - Colors as constants: `GREEN = "\033[0;32m"`, `YELLOW = "\033[1;33m"`, `RED = "\033[0;31m"`, `NC = "\033[0m"`
  - ASCII only in output (no `✓`, `✗`, `↔` — they fail on Windows cp1252)
  - `main() -> int`, `if __name__ == "__main__": sys.exit(main())`
  - `ROOT = Path(__file__).parent.parent`
- **Bash** (init.sh, close.sh):
  - `ok()`, `warn()`, `fail()` functions for output
  - `$PY` instead of `python3` or `python`
  - `set -euo pipefail` at the start

## Workflow to add a harness improvement

1. Identify which component the change affects (init.sh, close.sh, check_*.py, docs, …).
2. Read the whole file before editing — init.sh calls check_deps.py and
   check_contracts.py; close.sh calls init.sh.
3. If you add a new Python script: follow the check_deps.py/check_contracts.py pattern.
4. If you add a section to init.sh: insert before "Final result", use `$PY`, choose
   warn vs fail by severity.
5. Verify with `bash harness/init.sh` that everything passes.
6. If the change affects the harness architecture, update `harness/CHECKPOINTS.md`
   and the "Development harness" section of `CLAUDE.md`; if it alters the flow the
   agent follows (priorities, states, session steps), also update `AGENTS.md` and the
   `add-feature`/`add-bug` skills if they document that behavior.

## What NOT to do

- Do not add external dependencies to the harness Python scripts.
- Do not reorder close.sh's steps.
- Do not use `python3` directly — always `"$PY"`.
- Do not put non-ASCII characters in the output of harness Python scripts.
- Do not modify `harness/feature_list.json` directly from code — only via
  `/add-feature` and `/add-bug`.
- Do not turn informative checks (like "docs not updated") into `fail()`.
