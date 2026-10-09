# Verification — how to know your work functions

## Before marking a task `done`

1. Tests of what you touched green (`python -m pytest tests/test_<x>.py -q`), with the
   regression test if it was a bug.
2. Every `acceptance` criterion checked with the method it states.
3. No residue: no debug `print()`, context-less TODOs or temporary files.
4. `./harness/close.sh` runs the full suite (`init.sh`) before the commit.

## E2E verification (`verify` skill) — always opt-in

Starts the real app and walks the pages with a browser. It is expensive: only when the
user asks in the session ("verify the app", "/verify"), never on close or in `init.sh`.
A task's `E2E verification: yes/no` line is intent, not a trigger.

## Review — opt-in

`/code-review` is typed by the user. The model may launch a fresh-context reviewer
subagent over the diff of a non-trivial task or batch (see `orchestrate-backlog`).

## What `init.sh` verifies

- Python ≥ 3.9, harness files, coherent `feature_list.json` (a single `in_progress`,
  archive only `done`/`Cancelled`, unique ids) and dependencies (`check_deps.py`).
- Full pytest in parallel (`-n auto` if pytest-xdist is installed): the varying split
  across workers exposes shared state between files.
- UI↔core contracts (`check_contracts.py`) and placeholder text (`check_placeholder.py`).
- `pre-commit` hook (`check_comments.py --staged`) registered.

CI (`.github/workflows/ci.yml`) runs this same `init.sh` plus `check_comments.py` over the
pushed diff.
