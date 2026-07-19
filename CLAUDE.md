# <project-name> — project context

> **Template** — replace the `<placeholders>` when adopting the harness. This file is
> injected whole into every session: keep it minimal (**<40,000 characters always**,
> `close.sh` warns if exceeded). The detail lives in `harness/docs/`.

<One or two lines: what the project is, for whom, with which stack.>

**Where the detail lives (do not duplicate it here):**

- `harness/docs/architecture.md` — closed decisions and function-by-function module map.
- `harness/docs/data-models.md` — complete schema of the data files.
- `harness/progress/history.md` + `harness/feature_list.json` — changelog per session/feature.

## Architecture decisions (closed)

- **Stack:** <core in `core/` (independent of the UI) + UI in `ui/`>.
- <Closed decision 2: persistence, data sources, scope…>

## Paths

- <Relevant paths and folder structure of the project.>
- `docs/IDEAS.md` — the user's personal notebook, NOT actionable, no agent edits it.

## Module map (one line each; detail in `harness/docs/architecture.md`)

- `core/<module>.py` — <one line>.
- `ui/<page>.py` — <one line>.

## Development harness

- `harness/init.sh` — verifies the environment before working (Python, files, deps,
  tests, UI↔core contracts).
- `harness/close.sh` — session close: init.sh + docs checks (`check_docs.py` +
  40k-char limit of this file) + systemic bug→check cycle + archiving of closed
  features → `feature_list_archive.json` + archiving `current.md`→`history.md`
  + automatic conventional commit. Exit 3 = paused (fix the docs and re-run).
- `harness/check_contracts.py` / `check_docs.py` / `check_deps.py` /
  `check_placeholder.py` — deterministic checks.
- `harness/feature_list.json` — ACTIVE actionable backlog (manage ONLY with
  `/add-feature` and `/add-bug`); closed tasks (done/Cancelled) go to
  `harness/feature_list_archive.json` (global ids, maintained by `close.sh`).
- `harness/viewer.py` — Streamlit viewer (active+archived features, session log).
- `.claude/skills/verify/` — E2E verification of the real app; runs ONLY right before
  `close.sh` if the task declares `E2E verification: yes`, or on explicit user
  request — never in the init (see `AGENTS.md` §5 and `harness/docs/verification.md`).
- `.claude/skills/orchestrate-backlog/` — drain the backlog with sequential
  `implementer` subagents (haiku/sonnet, escalating to opus on the 2nd retry),
  code-review + E2E verify batched into one final pass and resumption after a session
  cut (persistent state in `harness/progress/orchestrator.md`).
- `.claude/agents/implementer.md` — native subagent with the implementation protocol
  for ONE backlog task (the orchestrator's prompt only carries the task's JSON).
- `.claude/settings.json` — versioned permissions: allow for harness commands, deny
  for writes to `docs/IDEAS.md` and `progress/history.md`.
- `harness/docs/` — architecture.md, data-models.md, conventions.md, verification.md.
- `harness/progress/` — `current.md` (active session) + `history.md` (historical log).

## Token and model optimization (orchestration)

When orchestrating work with subagents, minimize token consumption and delegate to
cheaper/faster models (e.g. Haiku or Sonnet) whenever the task allows:

- **Split heavy vs. light:** slice features into small, isolated tasks. Reserve the
  frontier model for architecture decisions, complex logic and deep debugging;
  delegate boilerplate, unit tests and repetitive refactors to smaller models with
  explicit, hyper-focused sub-prompts.
- **Minimal context:** do not pass whole multi-file structures to a subagent; only the
  target function/class and its direct dependencies.
- **No-filler sub-prompts:** subagent prompts demand direct output (only code or
  strict JSON/Markdown, no intros or explanations).
- **Summarized state:** before a new orchestration cycle, condense the history into a
  brief "State Summary" block (<200 tokens) instead of dragging the raw chat along.
- **Diffs only:** ask subagents for git diffs or concrete line replacements, never
  full-file rewrites.
- **Escalation, not insistence:** a failed task is retried once with the same model
  (passing it the concrete error) and a second time escalating one level
  (haiku→sonnet→opus); if that also fails, `blocked` and move on to the next.

## Backlog and future ideas

- `harness/feature_list.json` is the **only actionable backlog** (skills
  `/add-feature` and `/add-bug`).
- `docs/IDEAS.md` is the **user's personal notebook**: **no agent ever edits it** —
  not even to fix formatting. It is only read when the user explicitly asks to
  convert ideas into backlog features.

## Documentation maintenance

Every feature/bug that changes `core/`, `ui/` or the harness leaves the documentation
aligned **in the same session**, before `./harness/close.sh` (which verifies it).
**Each thing goes to its document — without duplication:**

1. `harness/docs/architecture.md` — the fine detail of what was implemented: new/
   renamed/removed public functions, design decisions, findings verified live (APIs,
   data series, behaviors). This is what `check_docs.py` cross-checks against the diff.
2. `harness/docs/data-models.md` — any schema change in a data file (new, renamed or
   removed key, or changed semantics).
3. `harness/progress/current.md` → `history.md` — the session's narrative changelog
   (archived by `close.sh`). NEVER write changelog in `CLAUDE.md` or architecture.md.
4. `CLAUDE.md` (this file) — ONLY if the one-line map changes (new/renamed/removed
   module or page), an architecture decision, or these rules. Keep it minimal:
   **below 40,000 characters always** (`close.sh` warns if exceeded).
5. `README.md` — only if the high-level picture changes (structure, usage, sync).
6. `harness/docs/conventions.md` / `verification.md` — only if a convention or the
   verification method changes.

Do not document future plans in any doc: actionable work lives in
`harness/feature_list.json`; unripe ideas in `docs/IDEAS.md`.

## Status

<Current phase of the project in 2-4 lines. Per-feature detail lives in
`harness/progress/history.md` and `harness/feature_list_archive.json`.>

## Commands

```bash
pip install -r requirements.txt
<app start command>
streamlit run harness/viewer.py    # backlog viewer
./harness/init.sh                  # verify the environment before working
./harness/close.sh                 # close the session and commit
```
