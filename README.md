# harness-agentes

Reusable development harness for working with AI agents (Claude Code) in an
**autonomous but verifiable** way: file-based backlog, deterministic checks, and a
session close with automatic commit.

Extracted from a real project in daily use (~770 tasks closed with this workflow), and
adapted to the Claude 5.5 models (Opus 5.5 with 1M context).

## How to work with it (Claude 5.5)

- **The main model implements.** One backlog task at a time, end to end: reads the code,
  changes it, runs the affected tests, logs in `harness/progress/current.md` and closes
  with `./harness/close.sh`. No long spec handed to a cheaper model: with the earlier
  "frontier specs → Haiku/Sonnet implements" flow, ~40% of tasks ended up as second-round
  bugs and specs grew to 3k characters dictating the solution. The real cost was the
  retries, not the implementation.
- **Subagents only where they pay off:** broad read-only exploration that returns
  conclusions, a fresh-context review of a non-trivial diff, and batches of mechanical,
  independent tasks (`/orchestrate-backlog` with Sonnet/Haiku `implementer`s).
- **Short specs.** `/add-feature` and `/add-bug` register what, why and verifiable
  criteria — not the how.
- **Expensive things are opt-in.** `/verify` (real app + browser) and `/code-review`
  run only when you ask.
- **Prune the harness instead of growing it.** A bug is closed with its root cause and a
  regression test; a new check only for a class of bug that keeps repeating.

## Philosophy

- **The repository is the system.** All state lives in versioned files: backlog
  (`feature_list.json`), active session (`progress/current.md`), session log
  (`progress/history.md`), technical docs (`harness/docs/`). No database, no state
  outside git.
- **Real verification, not impressions.** `init.sh` runs the full test suite in
  parallel, validates UI↔core contracts via AST and detects placeholder text. CI runs the
  same `init.sh`.
- **Minimal fixed context.** `AGENTS.md` is a map, not a bible. `CLAUDE.md` holds only
  decisions, paths and rules (<15k characters); `architecture.md` only decisions,
  invariants and verified findings (<60k) — with a large context window, reading the
  code is cheaper and more reliable than maintaining a prose mirror of it.

## Components

| Component | What it does |
|---|---|
| `AGENTS.md` | Agent entry point: map and the cycle of one task |
| `CLAUDE.md` | Minimal project context + how we work (template with placeholders) |
| `harness/init.sh` | Pre-work verification: Python, files, backlog, deps, tests, contracts, git hook |
| `harness/close.sh` | Task close: session log, size and comment gates, archiving, automatic commit |
| `harness/check_session_log.py` | `done` tasks must be narrated in `current.md` (else the commit loses its `#N`) |
| `harness/check_comments.py` | Comment length/density on changed files (pre-commit hook + close.sh) |
| `harness/check_contracts.py` | `ui/ → core/` imports point to real symbols (AST) |
| `harness/check_deps.py` | Undeclared third-party imports → added to `requirements.txt` |
| `harness/check_placeholder.py` | Placeholder text in `core/`/`ui/` string literals |
| `harness/rotate_history.py` | Size-based rotation of `history.md` into `progress/archive/` |
| `harness/hooks/pre-commit` | Runs `check_comments.py --staged` (registered by `init.sh`) |
| `harness/feature_list.json` | Active backlog; closed tasks go to `feature_list_archive.json` (global ids) |
| `harness/progress/` | `current.md` (active session) + `history.md` (append-only log) + `archive/` |
| `harness/docs/` | architecture.md · data-models.md · conventions.md · verification.md |
| `.claude/skills/add-feature` · `add-bug` | Register short-spec tasks in the backlog |
| `.claude/skills/orchestrate-backlog` | Process several tasks: main model + mechanical delegation, one review per batch |
| `.claude/skills/verify` | E2E verification with the real app and a browser (opt-in) |
| `.claude/agents/implementer.md` | Subagent that implements ONE bounded backlog task |
| `.claude/settings.json` | Versioned permissions (allow for the harness, deny for IDEAS.md/history/archive) |
| `.github/workflows/ci.yml` | CI: `init.sh` + `check_comments.py` over the pushed diff |

## Task lifecycle

```
./harness/init.sh                  # green environment before touching anything
  → pick ONE pending task (BUG_* bugs first)
  → implement + log in current.md
  → affected tests green, acceptance criteria checked one by one
  → mark done
./harness/close.sh                 # re-verifies, gates, archives, automatic commit (1-2 min)
```

Task states: `pending → in_progress → done` (or `blocked`); `close.sh` archives
`done`/`Cancelled` tasks and ids are never reused. `close.sh` is not reentrant: one run,
in the foreground, nothing in parallel.

## Adopting it in a new project

1. Copy the contents of this repo to the project root (or use it as a GitHub template).
2. Replace the `<placeholders>`:
   - `CLAUDE.md` — name, decisions, paths, code map, app start command.
   - `harness/feature_list.json` and `feature_list_archive.json` — `project` and `description`.
   - `.claude/skills/verify/SKILL.md` — `<app start command>` and `<app log file>`.
   - `harness/docs/` — fill in architecture/data-models and the UI section of conventions.md.
3. Create the expected layout folders: `core/`, `ui/`, `tests/`. The personal notebook
   `docs/IDEAS.md` is already included (delete the example idea).
4. `pip install pytest pytest-xdist` and run `./harness/init.sh` — it must finish green
   (with no tests yet it will WARN). It also registers the pre-commit hook.
5. Register the first task with `/add-feature` and work with the cycle above.

### Harness assumptions (adapt if your project differs)

- **Layered Python layout:** `core/` (logic) + `ui/` (presentation) + `tests/`. If you
  use other names, adjust `SCAN_DIRS`/`UI_DIRS`/`DIRS_PY`/`DIRS_JS` in the `check_*.py`
  scripts.
- **Python ≥3.9**, tests with pytest (unittest fallback; pytest-xdist optional), deps in
  `requirements.txt`.
- **Language:** everything in English (docs, UI and code). Adapt to your own language if
  you prefer — the parsed markers live in `close.sh`, `check_session_log.py`,
  `rotate_history.py` and `progress/current.md`.
- The scripts detect `python3`/`python` and force UTF-8: they work on macOS, Linux and
  Windows Git Bash.

## Credits

Based on the *harness engineering* pattern by
[betta-tech](https://github.com/betta-tech):
[ejemplo-harness-subagentes](https://github.com/betta-tech/ejemplo-harness-subagentes) and
[harness-sdd](https://github.com/betta-tech/harness-sdd). The implementation in this
repo is rewritten and extended (close with automatic commit, session-log and comment
gates, backlog archiving, history rotation, orchestration for the Claude 5.5 models), but the starting design —AGENTS.md as a map,
`feature_list.json` as the backlog, `init.sh` as the entry gate and `progress/` as
on-disk state— is theirs.

## License

[MIT](LICENSE)
