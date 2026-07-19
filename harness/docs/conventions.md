# Code conventions

## Python

- **Version:** Python 3.9+
- **Style:** PEP 8, maximum 100 characters per line
- **Names:**
  - Modules and functions: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE`
  - Private: `_` prefix
- **Strings:** double quotes. Interpolation with f-strings (no `.format()` or `%`).
- **Imports:** stdlib → external libraries → local modules. One group per type,
  separated by a blank line.
- **Language:** everything in English — docs, UI texts, code, keys and file names.

## Comments

By default **no** comments are written. They are only allowed when they explain the
**why** (a non-obvious constraint, a subtle invariant, a workaround with a reason).
Clear names communicate the what.

## `core/` modules

- Each module has a single responsibility (see `harness/docs/architecture.md`).
- Functions that can fail raise named exceptions, they do not return `None`.
- No mutable global state between calls.
- `core/` imports nothing from `ui/`: the core is reusable without the UI.

## UI (`ui/`)

- The UI contains no business logic. It calls `core/` for every computation.
- _Note here the start command and the UI framework version requirements._

## Tests (`tests/`)

- One test file per `core/` module: `tests/test_<module>.py`.
- Use `unittest.TestCase` with descriptive names.
- I/O tests use real temporary directories (no filesystem mocks).
- Run with: `python -m pytest tests/` or `python -m unittest discover tests/`.

## Harness (`harness/`)

- `init.sh` and `close.sh` run from the project root: `./harness/init.sh`.
- `check_*.py` and `viewer.py` are development tools, not production code.
- Harness scripts do not depend on the UI framework and must run in a clean shell
  (exception: `viewer.py`, which uses Streamlit).

## Documentation

Every feature/bug that changes `core/`, `ui/` or the harness leaves the documentation
aligned **in the same session**, before `./harness/close.sh` (which verifies it). Each
thing goes to its document, **without duplication**:

- `harness/docs/architecture.md` — the source of fine detail: new/renamed/removed
  public functions, design decisions, findings verified live.
- `harness/docs/data-models.md` — any schema change in a data file (new, renamed or
  removed key, or changed semantics).
- `harness/progress/current.md` — the session's narrative changelog (`close.sh`
  archives it into `history.md`). Never write changelog in `CLAUDE.md` or
  architecture.md.
- `CLAUDE.md` — ONLY if the one-line map changes (new/renamed/removed module or page)
  or an architecture decision. It stays below 40,000 characters (`close.sh` warns if
  exceeded).
- `README.md` — high-level picture; update only if the change affects what it describes.
- `harness/docs/conventions.md` / `verification.md` — only if a convention or the
  verification method changes.

Documentation describes **what is implemented**, never future plans: actionable work
goes to `harness/feature_list.json` (skills `/add-feature`, `/add-bug`); unripe ideas
go to `docs/IDEAS.md`, a **personal document of the user** that no agent edits (it is
only read when the user asks to convert ideas into features).
