# Verification — how to know your work functions

## Before declaring a feature `done`

1. **Run `./harness/init.sh`** — it must finish without errors (`[OK]` on every check,
   including the **UI↔core contracts** check).
2. **Green tests:** all tests of the affected module pass.
   ```bash
   python -m pytest tests/ -v
   ```
3. **E2E verification of the UI (`verify` skill):** if the task's `description` says
   `E2E verification: yes` (or, if it says nothing, when the change touches `core/` or
   `ui/`), run the `verify` skill (`.claude/skills/verify/SKILL.md`): it starts the
   real app, walks the affected pages interacting with the changed flow, and checks
   that there are no new errors in the app log or the terminal. Tests do not replace
   this step. It runs **only here** (once, right before `close.sh`) or when the user
   explicitly asks to verify — never at session start or in `init.sh`. If the task
   says `E2E verification: no`, skip this step.
4. **`acceptance` criteria one by one:** each criterion of the task in
   `harness/feature_list.json` states its verification method (test command or `UI:`
   step); verify them all before marking `done`.
5. **No residue:** no debug `print()`, context-less TODOs, or temporary files.

## Tests per layer

### core/
- `python -m pytest tests/test_<module>.py -v`
- For modules with I/O, use real temporary directories.
- For external API clients, mock the HTTP calls with `unittest.mock`.

### UI
- Start the app with its entry command (documented in `conventions.md`).
- Verify that the main pages load without exceptions in the terminal.

## Harness integrity checks

`./harness/init.sh` automatically verifies:
- Python 3.9+ installed.
- Mandatory files present (`AGENTS.md`, `harness/feature_list.json`,
  `harness/feature_list_archive.json`, `harness/progress/current.md`, `harness/docs/`).
- Only one feature in `in_progress` state at a time; the archive of closed tasks only
  contains `done`/`Cancelled` and there are no ids duplicated between active and archive.
- Tests executed correctly (in alphabetical order and in reverse order, to detect
  shared state between test files).
- **UI↔core contracts** (`harness/check_contracts.py`): every symbol `ui/` imports
  from `core/` actually exists. Catches runtime `AttributeError` and `ImportError`
  before the app starts. If this check fails, the app **will not start**.
- **Placeholder text** (`harness/check_placeholder.py`): no string literal in
  `core/`/`ui/` contains filler text from the blacklist.

## Session close

When the feature is `done`, run:
```bash
./harness/close.sh
```
The script verifies `init.sh`, detects whether `CLAUDE.md`/`README.md`/
`harness/docs/architecture.md` need updating — binary checks plus the deterministic
cross-check of `harness/check_docs.py`, which lists the public symbols of the diff
that are missing/leftover in the docs and the `core/`/`ui/` modules with no mention in
the README's Structure section —, and if the commit is a `fix` it reminds you of the
**systemic cycle**: which harness check would have caught the bug (add it with the
`improve-harness` skill, or note in `current.md` why it does not apply). Then it moves
`current.md` to `history.md`, resets it and makes the automatic commit.

Before `close.sh`, run `/code-review` over the session diff (fresh-context review) and
apply or reasonedly discard its findings (see `AGENTS.md` §5).
