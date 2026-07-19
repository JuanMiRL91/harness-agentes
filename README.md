# harness-agentes

Reusable development harness for working with AI agents (Claude Code) in an
**autonomous but verifiable** way: file-based backlog, deterministic checks, session
close with automatic commit, and token-optimized subagent orchestration.

Extracted from a real project in daily use (~190 features closed with this workflow).

## Philosophy

- **The repository is the system.** All state lives in versioned files: backlog
  (`feature_list.json`), active session (`progress/current.md`), session log
  (`progress/history.md`), technical documentation (`harness/docs/`). No database,
  no state outside git.
- **Real verification, not impressions.** `init.sh` actually runs the tests (twice:
  alphabetical and reverse order, to catch shared state), validates UI↔core contracts
  via AST and detects placeholder text. `close.sh` refuses to close a session with
  misaligned docs.
- **Progressive disclosure.** `AGENTS.md` is a map, not a bible: the agent reads each
  document only when it needs it. `CLAUDE.md` stays under 40k characters (the harness
  verifies it).
- **Systemic bug → check cycle.** Every closed bug forces the question of which harness
  check would have caught it earlier, and adds it in the same session.
- **Tokens as a scarce resource.** The frontier model orchestrates and decides;
  subagents (Haiku/Sonnet) implement. Review and E2E verification are batched at the
  end of the run, not per feature.

## Components

| Component | What it does |
|---|---|
| `AGENTS.md` | Agent entry point: how to pick a task, hard rules, lifecycle |
| `CLAUDE.md` | Minimal project context (template with placeholders) |
| `harness/init.sh` | Pre-work verification: Python, files, backlog, deps, tests, contracts |
| `harness/close.sh` | Session close: docs checks, archiving, automatic conventional commit |
| `harness/check_contracts.py` | `ui/ → core/` imports point to real symbols (AST) |
| `harness/check_docs.py` | Public symbols in the diff cross-checked against docs; modules against README |
| `harness/check_deps.py` | Undeclared third-party imports → added to `requirements.txt` |
| `harness/check_placeholder.py` | Placeholder text in `core/`/`ui/` string literals |
| `harness/feature_list.json` | Active backlog; closed tasks go to `feature_list_archive.json` (global ids) |
| `harness/progress/` | `current.md` (active session) + `history.md` (append-only log) |
| `harness/docs/` | architecture.md · data-models.md · conventions.md · verification.md |
| `harness/CHECKPOINTS.md` | Objective criteria for a "correct final state" |
| `harness/viewer.py` | Streamlit viewer for the backlog and the session log |
| `.claude/skills/add-feature` · `add-bug` | Register tasks in the backlog with schema and validation |
| `.claude/skills/improve-harness` | Extend the harness itself (internal map + conventions) |
| `.claude/skills/orchestrate-backlog` | Drain the backlog with sequential subagents + batched review/verify |
| `.claude/skills/verify` | E2E verification with the real app and a browser (expensive: close-time only) |
| `.claude/agents/implementer.md` | Subagent that implements ONE backlog task |
| `.claude/settings.json` | Versioned permissions (allow for the harness, deny for IDEAS.md/history.md) |

## Session lifecycle

```
./harness/init.sh                  # green environment before touching anything
  → pick ONE pending task (BUG_* bugs first)
  → implement + document in current.md in real time
  → verify acceptance criteria one by one (+ verify skill if the task declares it)
  → /code-review over the diff
  → mark done
./harness/close.sh                 # re-verifies, cross-checks docs, archives, automatic commit
```

Task states: `pending → in_progress → done` (or `blocked`); `close.sh` archives
`done`/`Cancelled` tasks and ids are never reused.

## Adopting it in a new project

1. Copy the contents of this repo to the project root (or use it as a GitHub
   template).
2. Replace the `<placeholders>`:
   - `CLAUDE.md` — name, decisions, paths, module map, app start command.
   - `harness/feature_list.json` and `feature_list_archive.json` — `project` and `description`.
   - `.claude/skills/verify/SKILL.md` — `<app start command>` and `<app log file>`.
   - `harness/docs/` — fill in the architecture/data-models templates and the UI
     section of conventions.md.
3. Create the expected layout folders: `core/`, `ui/`, `tests/`. The personal
   notebook `docs/IDEAS.md` is already included (delete the example idea).
4. Run `./harness/init.sh` — it must finish green (with no tests yet it will WARN).
5. Register the first task with `/add-feature` and work with the cycle above.

### Harness assumptions (adapt if your project differs)

- **Layered Python layout:** `core/` (logic) + `ui/` (presentation) + `tests/`.
  If you use other names, adjust `SCAN_DIRS`/`UI_DIRS` in the `check_*.py` scripts and
  the `core/ ui/` paths in `init.sh`/`close.sh`.
- **Python ≥3.9**, tests with pytest (unittest fallback), deps in `requirements.txt`.
- **Language:** everything in English (docs, UI and code). Adapt to your own language
  if you prefer — the parsed markers live in `close.sh` and `progress/current.md`.
- `check_docs.py` cross-checks `core/*.py` and `ui/common.py` (the UI's public
  boundary); extend the list if your UI exposes more documentable modules.
- The scripts detect `python3`/`python` and force UTF-8: they work on macOS, Linux and
  Windows Git Bash.

## Credits

Based on the *harness engineering* pattern by
[betta-tech](https://github.com/betta-tech):
[ejemplo-harness-subagentes](https://github.com/betta-tech/ejemplo-harness-subagentes) and
[harness-sdd](https://github.com/betta-tech/harness-sdd). The implementation in this
repo is rewritten and extended (close with automatic commit and documentation checks,
backlog archiving, systemic bug→check cycle, orchestration with model escalation and
batched E2E verification), but the starting design —AGENTS.md as a map,
`feature_list.json` as the backlog, `init.sh` as the entry gate and `progress/` as
on-disk state— is theirs.

## License

[MIT](LICENSE)
