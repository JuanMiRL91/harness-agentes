# CHECKPOINTS — Final-state evaluation

Five objective checkpoints. The reviewing agent validates them before closing any session.

---

## C1 — Complete harness

- [ ] These exist: `AGENTS.md`, `harness/init.sh`, `harness/feature_list.json`, `harness/feature_list_archive.json`, `harness/progress/current.md`, `harness/progress/history.md`
- [ ] These exist: `harness/docs/architecture.md`, `harness/docs/data-models.md`, `harness/docs/conventions.md`, `harness/docs/verification.md`
- [ ] `CLAUDE.md` is 40,000 characters or fewer (the detail lives in `harness/docs/`)
- [ ] `./harness/init.sh` runs without errors

## C2 — Coherent state

- [ ] Only one feature `in_progress` (or none)
- [ ] `feature_list_archive.json` contains only `done`/`Cancelled`, with no ids duplicated with the active file (`init.sh` §3 validates it)
- [ ] `done` features have passing tests
- [ ] `harness/progress/current.md` contains only the active session (no accumulation of previous sessions)

## C3 — Architectural compliance

- [ ] `core/` contains only the modules documented in `harness/docs/architecture.md`
- [ ] The UI (`ui/`) contains no business logic
- [ ] No external dependencies undeclared in `requirements.txt`
- [ ] No debug code (leftover `print()`, context-less TODOs)

## C4 — Genuine verification

- [ ] Every `core/` module has at least one test in `tests/`
- [ ] Tests use real temporary directories (no filesystem mocks)
- [ ] `python -m pytest tests/` finishes green

## C5 — Correct session close

- [ ] No untracked temporary files in git
- [ ] The session is documented in `harness/progress/history.md`
- [ ] Feature states in `harness/feature_list.json` reflect the work actually completed
- [ ] `./harness/close.sh` executed successfully (automatic commit made)

---

A reviewer validates each checkpoint systematically. If any fails, the session does not close.
