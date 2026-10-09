---
name: orchestrate-backlog
description: Process several pending tasks of the project backlog (harness/feature_list.json) in the same session, one after another, with one commit per task via close.sh; the main model implements the non-trivial ones and delegates the mechanical ones to implementer subagents. Use it when the user asks to "drain/process the backlog", "get the pending tasks to done", "go through the features", a /goal over several tasks, or working on more than one backlog task in the session — even if they do not say "orchestrate".
---

# Processing the backlog

Always sequential (tasks share `feature_list.json`, `current.md` and git): one task, its
`close.sh`, the next one.

## 1. Plan (once)

1. `./harness/init.sh` green.
2. List the `pending` tasks (`BUG_` first by id, then features by id) and read each one.
3. Decide who does each and show it in a short table (do not ask for confirmation):
   - **Main model** — by default: `core/` logic, new UI, anything crossing layers or
     needing judgment. It implements directly with the `AGENTS.md` cycle.
   - **`implementer` (sonnet)** — bounded, independent tasks with clear criteria.
   - **`implementer` (haiku)** — purely mechanical (rename, delete a block, change a
     default).
4. Write in `harness/progress/orchestrator.md`: the table, `Batch base: <git rev-parse
   HEAD>` and an empty `## Deferred verify`. It is the state to resume from if the
   session dies.

## 2. Execution

- **The main model's tasks:** normal cycle (`AGENTS.md` §2) up to `close.sh`'s commit.
- **Delegated ones:** `implementer` agent with the plan's `model`, `run_in_background:
  false`, prompt = the task's literal JSON entry + 1-3 lines of context if relevant. Its
  protocol lives in `.claude/agents/implementer.md`: do not repeat it.
- After each task: `git log --oneline -1` contains `(#<id>)`, `git status --short` empty,
  `pgrep -f harness/close.sh` returns nothing. `UI:` criteria → `## Deferred verify`.
- If a delegated task fails: one retry via SendMessage with the concrete error; if it
  fails again, do it yourself (main model) with clean context. If that also fails,
  `blocked` and move on.

## 3. Closing the batch

1. **Review:** for the batch diff (`git diff <Batch base>..HEAD`) launch a fresh-context
   reviewer subagent (general-purpose) that returns confirmed findings with file:line;
   or ask the user to type `/code-review` (the model cannot invoke it). Real findings →
   `/add-bug` and fix them in this same batch. A single review pass per batch.
2. **E2E verify:** only if the user asks. If there is `Deferred verify`, say so in one
   line and ask; if they accept, `/verify` ONCE over the union of pages, criterion by
   criterion.
3. Leave `orchestrator.md` with `_no active orchestration_` and commit it
   (`chore: close of batch #N..#M`).

## Usage limit

Only if the user warns or a turn fails due to rate limit with a reset time: launch
nothing else, keep `orchestrator.md` up to date and schedule with CronCreate a one-shot at
the reset time +5 min with the prompt "Invoke the orchestrate-backlog skill and resume
from harness/progress/orchestrator.md". No periodic crons.

## Large independent batches

If the user explicitly asks for it ("use a workflow"), the Workflow tool can parallelize
exploration or review; implementation stays sequential.
