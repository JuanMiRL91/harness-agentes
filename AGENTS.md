# AGENTS.md — entry point for AI agents

A map, not a rulebook: read only what you need. Project context and rules live in
`CLAUDE.md`; here, only the cycle of one task.

## 1. Map

| Where | What | When |
|---|---|---|
| `CLAUDE.md` | Decisions, paths, code map, rules | Always |
| `harness/feature_list.json` | Active backlog (closed tasks in `feature_list_archive.json`, global ids) | When picking a task |
| `harness/progress/current.md` | Session in progress | At start and while working |
| `harness/progress/history.md` | Session log (old ranges in `progress/archive/`) | Only with `grep`, never whole |
| `harness/docs/architecture.md` | Decisions, invariants, verified findings | Before touching an area |
| `harness/docs/data-models.md` | Schema of every data file | Before touching data |
| `harness/docs/conventions.md` | Style, tests, harness, documentation | When in doubt |
| `harness/docs/verification.md` | How to verify | Before marking `done` |
| `core/` · `ui/` · `tests/` | Logic · presentation · tests | To implement |
| `docs/IDEAS.md` | The user's personal notebook — **never edit it** | Only if the user asks |

## 2. Cycle of one task

1. `./harness/init.sh` green (if it fails, stop and fix it first). CI runs this same
   `init.sh`.
2. Pick ONE `pending` task: `BUG_*` first by lowest id, otherwise the lowest-id feature.
   ```bash
   python3 -c "
   import json
   fs = [f for f in json.load(open('harness/feature_list.json'))['features'] if f['status']=='pending']
   fs.sort(key=lambda f: (not f['name'].upper().startswith('BUG'), f['id']))
   print(fs[0]['id'], fs[0]['name'], '·', fs[0]['title']) if fs else print('Nothing pending')
   "
   ```
3. Mark it `in_progress` and open `current.md` with `- **Feature in progress:** #N name`
   (the `#N` first: `close.sh` parses it).
4. Implement. Bug = root cause + regression test. Tests of what you touched green and
   every `acceptance` criterion checked with its method. `UI:` criteria are verified
   with `/verify` only if the user asks.
5. Docs in the same session if a decision changes (`architecture.md`) or a data schema
   (`data-models.md`); a brief log in `current.md`.
6. Mark `done` and run `./harness/close.sh` ONCE, in the foreground, `timeout: 600000`,
   nothing in parallel (it is not reentrant). Exit 0 = commit made · 1 = error ·
   3 = paused: fix what it points out and re-run. If the call times out, wait
   (`while pgrep -f harness/close.sh >/dev/null; do sleep 5; done`) before deciding
   anything; never kill it.

## 3. If you get stuck

Look in `harness/docs/` or `CLAUDE.md` before inventing. If the tool does not do what you
expect, do not improvise a workaround: note it in `current.md` and stop.
