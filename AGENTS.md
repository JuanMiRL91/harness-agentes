# AGENTS.md — Navigation map for AI agents

> This file is the **entry point** for any agent working in this repository. It is
> NOT a rulebook bible: it is a **map**. Read only what you need when you need it
> (progressive disclosure).

---

## 1. Before starting (mandatory)

1. Run `./harness/init.sh` and verify it finishes without errors. If it fails,
   **stop** and fix the environment before touching code.
2. Read `harness/progress/current.md` to understand the state the last session
   ended in.
3. Read `harness/feature_list.json` and pick **one** task with `pending` status. Do
   not work on more than one at a time. **Bugs go first**: if there is any `pending`
   task whose `name` starts with `BUG_`, take it before any feature (see §4 for the
   exact criterion).

## 2. Repository map

| File / folder                  | What it contains                                                    | When to read it        |
|--------------------------------|---------------------------------------------------------------------|------------------------|
| `harness/feature_list.json`    | ACTIVE backlog (pending / in_progress / blocked); done/Cancelled are archived in `feature_list_archive.json` (global ids) | Always, when starting  |
| `harness/progress/current.md`  | Current session state                                               | Always, when starting  |
| `harness/progress/history.md`  | Append-only log of previous sessions                                | If you need historical context |
| `harness/docs/architecture.md` | Design decisions and function-by-function module map (fine detail)  | Before implementing    |
| `harness/docs/data-models.md`  | Complete schema of the data files                                   | Before touching data   |
| `harness/docs/conventions.md`  | Style, naming and structure rules                                   | Before writing code    |
| `harness/docs/verification.md` | How to verify that your work functions                              | Before declaring `done` |
| `harness/CHECKPOINTS.md`       | Objective criteria for a "correct final state"                      | To self-evaluate       |
| `CLAUDE.md`                    | Minimal project context (decisions, paths, one-line map)            | At session start       |
| `core/`                        | Python core (business logic, independent of the UI)                 | To implement           |
| `ui/`                          | UI (no business logic; calls `core/`)                               | For UI work            |
| `harness/`                     | Development tools: init.sh, close.sh, check_*.py, viewer.py         | For the harness        |
| `tests/`                       | Automated tests                                                     | To verify              |
| `docs/IDEAS.md`                | The user's **personal** notebook (future ideas) — **NEVER edit it** | Only if the user asks to analyze it |

## 3. Hard rules (non-negotiable)

- **One feature at a time.** Do not mix changes from several tasks in the same session.
- **Do not declare a task `done` without green tests.** Run `./harness/init.sh` and
  make sure the tests block passes 100%.
- **Document what you do** in `harness/progress/current.md` while you work, not at the end.
- **Update the affected documentation in the same session** — each thing goes to its
  document, without duplication: module/function/decision detail →
  `harness/docs/architecture.md`; data schema changes → `harness/docs/data-models.md`;
  changelog → `harness/progress/current.md` (archived by `close.sh` into `history.md`);
  `CLAUDE.md` ONLY if the one-line map or an architecture decision changes (keep it
  <40k characters); `README.md` only if the high-level picture changes. See
  "Documentation maintenance" in `CLAUDE.md`; `close.sh` verifies it.
- **Always close the session with `./harness/close.sh`** — it makes the automatic commit.
- **If you don't know something, look in `harness/docs/` or `CLAUDE.md`** before
  inventing it.
- **`docs/IDEAS.md` is untouchable:** it is the user's personal notebook. Do not edit
  it, do not reformat it, do not "complete" it. It is only read when the user asks to
  convert their ideas into `harness/feature_list.json` features.

## 4. How to pick a task

**Bugs take priority over features.** A bug is any task whose `name` starts with
`BUG_`. Among the `pending` ones, bugs first by lowest `id`; if no `pending` bug
remains, the `pending` feature with the lowest `id`.

```
1. Open harness/feature_list.json
2. Filter by status == "pending"
3. If there are bugs (name starts with "BUG_"): take the bug with the lowest "id"
   If there are no pending bugs: take the feature with the lowest "id"
4. Change its status to "in_progress" and save
5. Note in harness/progress/current.md: feature, start time, brief plan
```

The "Feature in progress" line of `current.md` must follow the format
`#N feature_name` (the `#N` first) — `close.sh` parses it to title the session in
`history.md`.

To pick deterministically:

```bash
python3 -c "
import json
fs = [f for f in json.load(open('harness/feature_list.json'))['features'] if f['status']=='pending']
fs.sort(key=lambda f: (not f['name'].upper().startswith('BUG'), f['id']))
print('Next:', fs[0]['id'], fs[0]['name'], '·', fs[0]['title']) if fs else print('Nothing pending')
"
```

## 5. Session close (lifecycle)

When the feature is complete:

1. **Verify the `acceptance` criteria one by one** with the method each one states
   (test command, or `UI:` step with the `verify` skill, which starts the real app).
   Do not mark `done` with unchecked criteria. The `verify` skill runs **once and only
   here** (right before `close.sh`), and only if the task's `description` says
   `E2E verification: yes` (or has `UI:` steps in `acceptance`); if it says
   `E2E verification: no`, skip it. NEVER run it at session start or as part of
   `init.sh` — it is the most token-expensive skill in the harness.
2. **If the task was a `BUG_`, also close the systemic cycle:** ask yourself which
   harness check (`init.sh`, `close.sh`, `check_*.py`, a test) would have caught this
   bug before it reached the user. If a reasonable one exists, add it **in the same
   session** (`improve-harness` skill); if it does not apply, note in
   `harness/progress/current.md` a line `Systemic check: not applicable — <reason>`.
   `close.sh` will remind you if you close a fix without touching `harness/`.
3. **Fresh-context review:** run `/code-review` over the session diff before the
   commit and apply (or reasonedly discard, leaving it in `current.md`) the findings.
   Exception: in a backlog orchestration (`orchestrate-backlog` skill) the review is
   batched at the end of the run — the implementer subagent does NOT run it per feature.
4. Mark `status: "done"` in `harness/feature_list.json`.
5. Run `./harness/close.sh` — it does everything else automatically:
   - Verifies that `init.sh` passes 100%.
   - Warns if neither `harness/docs/architecture.md` nor `harness/docs/data-models.md`
     were touched while there are changes in `core/`/`ui/`, cross-checks the public
     symbols of the diff against the docs and the module list against the README
     (`harness/check_docs.py`) and warns if `CLAUDE.md` exceeds 40,000 characters.
   - If the commit is a `fix`, reminds you of the systemic bug → harness check cycle.
   - Archives `done`/`Cancelled` features into `harness/feature_list_archive.json`.
   - Moves the `harness/progress/current.md` summary to the end of
     `harness/progress/history.md`.
   - Resets `harness/progress/current.md` to the template.
   - Makes the commit with a conventional message (`feat(#N)` / `fix(#N)`).

   Exit codes: `0` = closed · `1` = error · `3` = **paused** (docs pending or
   `CLAUDE.md` >40k) — fix exactly what it points out and re-run `./harness/close.sh`;
   never try to bypass the warning (with non-interactive stdin the pause is automatic).

## 6. If you get stuck

- Re-read the relevant section of `harness/docs/` or `CLAUDE.md`.
- If the tool does not do what you expect, **do not invent a workaround**: document
  the blocker in `harness/progress/current.md` and stop the session.

---
