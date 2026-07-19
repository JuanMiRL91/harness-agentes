---
name: orchestrate-backlog
description: Orchestrate draining the project backlog (harness/feature_list.json) by delegating each pending task to sequential Haiku/Sonnet subagents and batching the E2E verification (verify skill) into ONE final pass, to minimize tokens and not exhaust the 5-hour limit. Use it WHENEVER the user asks to "get the pending features to done", "drain/process the backlog", "run agents through the features", a /goal over several feature_list.json tasks, or any request to work on more than one backlog task in the same session — even if the word "orchestrate" is not mentioned.
---

# Orchestrating the backlog with subagents

The main chat (frontier model) acts ONLY as orchestrator: it plans, delegates,
supervises and verifies at the end. **It never implements code itself** — every line
of implementation the orchestrator writes is the most expensive possible use of
tokens. The three token sinks this skill eliminates:

1. **One `/verify` per feature.** The `verify` skill (real app + browser) is the most
   expensive one in the harness. If several features touch the same pages, a single
   batched pass at the end covers them all.
2. **One `/code-review` per feature.** A subagent reviewing itself with its own
   context adds little: the review is batched at the end, a single pass with fresh
   context over the whole batch diff.
3. **Each subagent re-deriving the protocol.** The implementation protocol lives in
   the **`implementer`** agent (`.claude/agents/implementer.md`), not in the prompt:
   each subagent only receives the literal JSON entry of its task.

## Phase 1 — Inventory and plan (orchestrator, once)

1. `./harness/init.sh` — if it fails, stop and fix it before delegating anything.
2. List the `pending` tasks sorted (`BUG_` bugs first by id, then features by id):

   ```bash
   python3 -c "
   import json
   fs = [f for f in json.load(open('harness/feature_list.json'))['features'] if f['status']=='pending']
   fs.sort(key=lambda f: (not f['name'].upper().startswith('BUG'), f['id']))
   for f in fs: print(f['id'], f['name'], '·', f['title'])
   "
   ```

   (Closed tasks live in `harness/feature_list_archive.json`; pending ones, always in
   the active file.)

3. Read the full entry of each pending task (once; keep them for the prompts) and
   classify them into a plan with three columns per task:
   - **Model:** `haiku` only for mechanical changes (changing a default, renaming,
     deleting a delimited block, grep-verifiable criteria); `sonnet` for everything
     else (`core/` logic, new UI, tests with edge cases). The frontier model never
     implements.
   - **E2E:** `yes`/`no` per the `E2E verification:` line of the `description`; if
     absent, `yes` when there are `UI:` criteria in `acceptance` or it touches
     `core/`/`ui/` (the `verify` skill's default criterion).
   - **Verify group:** the pages/tabs to walk (from the E2E line or the `UI:` steps).
     Tasks with common pages share a group.
4. Create/update `harness/progress/orchestrator.md` with the plan, a line
   `Batch base: <hash from git rev-parse HEAD>` (anchor for Phase 3's batched review)
   and an empty `## Deferred verify` section. This file is the orchestration's
   persistent state: if the session dies (5h limit, close), the next invocation of
   this skill reads it and continues where it left off. Show the plan to the user in
   a short table before starting (do not ask for confirmation: invoking the skill is
   the order).

## Phase 2 — One subagent per task (sequential, never in parallel)

Tasks share files (`feature_list.json`, `current.md`, git) and the repo rule is one
feature at a time: launch the subagents **one by one** and wait for the result
(`run_in_background: false`).

Launch each task with the **`implementer`** agent — its full protocol lives in
`.claude/agents/implementer.md`, do NOT duplicate it in the prompt — passing the
plan's `model` (`haiku` mechanical · `sonnet` the rest). Minimal prompt:

```
TASK (harness/feature_list.json):
<full JSON entry, literal>
```

plus, only if applicable, 1-3 lines of specific context (relation to another task in
the batch, a decision already made by the user).

After each subagent, the orchestrator (cheap, without re-reading large files):

- Confirms the commit: `git log --oneline -1` contains `(#<id>)`; and the `done`
  status with a one-liner (NOTE: close.sh archives the entry on close — look for it
  in both files):

  ```bash
  python3 -c "
  import json
  fid = <id>
  for p in ('harness/feature_list.json', 'harness/feature_list_archive.json'):
      for f in json.load(open(p))['features']:
          if f['id'] == fid: print(p, '->', f['status'])
  "
  ```

- **Retry ladder** if there is no commit or the status is not `done`:
  1. Relaunch the same subagent ONCE via SendMessage with the concrete error
     (keeps its context).
  2. If it fails again, launch a NEW `implementer` with the model one level up
     (`haiku`→`sonnet`, `sonnet`→`opus`); prompt = JSON entry + summary of what was
     tried and what error it gave (clean context: do not drag the transcript along).
  3. If that also fails, mark the task `blocked` in `orchestrator.md`'s plan and move
     on to the next (do not fix it yourself in the main chat unless it is trivial).
- Add the task's `UI:` criteria to `## Deferred verify` in `orchestrator.md`.
- Do not drag the chat along: your state is 3-4 lines per task (the State Summary),
  not the subagent's transcript.

## Phase 3 — Batched review and verify (once, at the end)

When no pending tasks remain (or when resuming an orchestration with a non-empty
`## Deferred verify`):

1. **Batched review:** run the `code-review` skill (effort medium) ONCE over the
   whole batch diff (`git diff <Batch base>..HEAD`; the hash is in
   `orchestrator.md`). Confirmed findings → register them as `BUG_` (conventions of
   the `add-bug` skill) and close them with `implementer` subagents (sonnet) via the
   Phase 2 protocol. A single review pass per orchestration: the commits of these
   fixes do NOT re-trigger another review.
2. **Batched verify:** run the `verify` skill ONCE over the **union** of pages/tabs
   in `## Deferred verify`, explicitly checking each deferred `UI:` criterion (not a
   generic walkthrough: each criterion, its measured result). It goes after the
   review to also cover its fixes.
3. If everything passes: empty `orchestrator.md` (leave it with the header and
   "_no active orchestration_") and commit that close as
   `chore: batched verify of #N..#M` (here yes, a direct commit — there is no feature
   to close).
4. If the verify fails something: the features' commits already exist — fix forward.
   Register the failure as `BUG_` (conventions of the `add-bug` skill), launch an
   `implementer` (sonnet) for the fix via the Phase 2 protocol, and repeat the failed
   check. Do not repeat the whole pass if the other criteria already passed.

## 5-hour limit — resumption

The design is already cut-tolerant: `feature_list.json` (status), git (commits per
feature) and `orchestrator.md` (plan + deferred verify) reconstruct the full state;
resuming = invoking this skill again.

There is no reliable way to read the usage % from inside the session: do not check
or estimate it. The only valid triggers are that **the user warns** ("limit at 90%",
"it ran out, resets at 18:00") or that **a turn fails due to rate limit** with a
visible reset time. In that case:

- **Do not launch more subagents**: a half-done feature with the limit exhausted
  leaves the repo dirty. Leave `orchestrator.md` up to date.
- Schedule the resumption with **CronCreate**: a **one-shot** cron at the reset time
  **+5 min margin**, with the prompt: "Invoke the orchestrate-backlog skill and
  resume the orchestration from harness/progress/orchestrator.md". Confirm to the
  user the scheduled time and that the session must stay open (one-shot crons only
  fire with the session alive or resumed with --resume/--continue; they expire after
  7 days). If CronCreate is not available, say so and ask the user to reopen the
  chat with that same sentence after the reset.
- After resuming, delete the cron if it is still listed (CronDelete) and continue
  Phase 2.

Do not schedule periodic crons "just in case": they would burn turns of the new limit.

## What NOT to do

- Do not implement code in the main chat (frontier) — not even "quick fixes".
- Do not launch subagents in parallel over the backlog (shared files + one feature
  at a time rule).
- Do not run `verify` or `code-review` per feature: both are batched at the end.
- Do not duplicate the implementer's protocol in the prompt (it lives in
  `.claude/agents/implementer.md`); the prompt is the JSON entry + occasional context.
- Do not pass whole AGENTS.md/CLAUDE.md/architecture.md files in the subagent's
  prompt: the subagent reads concrete files only if the task cites them.
- Do not skip close.sh's warnings: exit 3 = fix what it points out and re-run.
- Never touch `docs/IDEAS.md`.
