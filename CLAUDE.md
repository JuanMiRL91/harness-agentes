# <project-name> — project context

> **Template** — replace the `<placeholders>` when adopting the harness. This file is
> injected whole into every session: decisions, paths and rules only (**< 15,000
> characters**, `close.sh` enforces it). Detail lives in `harness/docs/` and in the code.

<One or two lines: what the project is, for whom, with which stack.>

Detail (do not duplicate it here): `harness/docs/architecture.md` (decisions, invariants,
findings) · `harness/docs/data-models.md` (schema of every data file) ·
`harness/docs/conventions.md` (style, tests, harness).

## Architecture decisions (closed)

- **Stack:** <core in `core/` (independent of the UI) + UI in `ui/`>.
- <Closed decision 2: persistence, data sources, scope…>

## Code map (area grain; the detail is in the code itself)

- `core/` — <one line per area, not per function>.
- `ui/` — <one line>.

## Paths

- <Relevant paths and folder structure of the project.>
- `docs/IDEAS.md` — the user's personal notebook, NOT actionable, no agent edits it.

## How we work (Claude 5.5 models)

- **By default the main model implements directly**, one backlog task at a time: reads
  the code involved, changes it, runs the affected tests, leaves the log in
  `harness/progress/current.md` and closes with `./harness/close.sh` (automatic commit).
  It does not write a long spec for someone else to implement.
- **Subagents only for what parallelizes or isolates:** broad read-only exploration
  (Explore/Sonnet, returning conclusions, not file dumps), a fresh-context review of the
  diff of a non-trivial task, and batches of mechanical, independent tasks (`implementer`
  agent with Sonnet/Haiku via `/orchestrate-backlog`). Say which model (and effort) each
  subagent uses.
- **Backlog:** `harness/feature_list.json` is the only actionable backlog (`/add-feature`,
  `/add-bug`). Bugs (`BUG_*`) before features. Specs are short: what, why and verifiable
  criteria; the how only when there is a hard constraint.
- **A bug = root cause + regression test** that fails without the fix. A new harness
  check only for a class of bug that keeps repeating.
- **`/verify` (E2E with a browser) and `/code-review` are opt-in:** only when the user
  asks. `/code-review` is typed by the user (the model cannot invoke it).
- **Analysis ≠ changes:** for "review/analyze/tell me if…", deliver the diagnosis without
  touching code.
- **Never:** edit `docs/IDEAS.md`, `harness/progress/history.md` or
  `harness/progress/archive/` (blocked by `.claude/settings.json`); commit/push outside
  `close.sh` unless asked.

## Documentation (each thing in its place, no duplication)

- `architecture.md`: decisions, invariants and verified findings; not a function index.
  `data-models.md`: every data schema change. `current.md`: the session changelog. This
  file: only if a decision, a path or a rule changes. `README.md`: vision and way of working.
- No future plans in the docs: actionable work goes to the backlog, ideas to `IDEAS.md`.
- Sparse comments: ≤ 2 lines each and ≤ 1 per 5 lines of code in touched files
  (`harness/check_comments.py`, pre-commit hook).

## Commands

```bash
pip install -r requirements.txt
<app start command>
./harness/init.sh                  # verify the environment (tests + checks)
./harness/close.sh                 # close a task: init + log + archiving + commit
```

`close.sh`: exit 0 closed · 1 error (init red or task not `done`) · 3 paused (session log,
comments or doc size: fix and re-run). One run, in the foreground, `timeout: 600000`,
nothing in parallel while it runs.
