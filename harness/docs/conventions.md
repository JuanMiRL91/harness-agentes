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
**why** (a non-obvious constraint, a subtle invariant, a workaround with a reason). Clear
names communicate the what.

Enforced by `harness/check_comments.py` (`pre-commit` hook in `harness/hooks/`, registered
by `init.sh`; and `close.sh` §3b) on the **changed** files (`.py` under
`core/ui/harness/tests/scripts`, `.ts/.tsx/.js/.jsx` under `ui/`):

- **Length:** no comment block exceeds **2 lines**.
- **Density:** in a file with ≥15 lines of code, at most **1 comment line per 5 of code**.
- **Module/class docstrings:** in a `.py` of ≥20 lines they stay under **30% of the
  file**. Function docstrings are excluded: they are the public contract. Design
  decisions go to `harness/docs/architecture.md`.
- Pragmas (`# noqa`, `# type:`…) do not count. Legacy code blocks nothing until touched.
  Skip once: `git commit --no-verify`.

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
- I/O tests use real temporary directories (`tmp_path`), never real user data. Network
  always mocked.
- A fixed bug leaves a regression test that fails without the fix.
- Full suite: `python -m pytest tests/ -q -n auto` (pytest-xdist); during a task, the
  affected files are enough.

## Harness (`harness/`)

- `init.sh`/`close.sh` run from the root. `close.sh` takes 1-2 min and is not reentrant:
  one run, in the foreground (`timeout: 600000`), nothing in parallel.
- Closing a task requires `- **Feature in progress:** #N name` and a brief log in
  `harness/progress/current.md` (`check_session_log.py`); the `feat(#N)`/`fix(#N)` commit
  and the `history.md` entry come from there.
- Checks that can `exit` run before the task archiving in `close.sh`.
- A new check is added only for a **class** of bug that repeats or that a test cannot
  cover; a one-off bug is covered by its regression test.
- Harness scripts are stdlib-only, print ASCII (Windows cp1252) and use `"$PY"`, never
  `python3` directly.

## Documentation

Each thing in its place, without duplication and only what the code does not say:

- `harness/docs/architecture.md` — decisions, invariants and verified findings (external
  APIs, non-obvious behaviors). Not a function index: the code and its docstrings are.
  ≤ 60,000 characters (`close.sh`).
- `harness/docs/data-models.md` — every schema change of a data file.
- `harness/progress/current.md` — the session changelog (`close.sh` archives it).
- `CLAUDE.md` — decisions, paths and rules only; < 15,000 characters (`close.sh`).
- `README.md` — high-level vision and the user's way of working.

Never future plans in the docs: actionable work goes to `harness/feature_list.json`
(`/add-feature`, `/add-bug`); ideas to `docs/IDEAS.md`, which no agent edits.
