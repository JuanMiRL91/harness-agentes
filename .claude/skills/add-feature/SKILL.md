---
name: add-feature
description: Add one or several new tasks to the harness backlog (harness/feature_list.json) of the project, in "pending" status and following the repo conventions. Use it when the user asks to "add a feature/task", "new feature", or describes implementations to register in the backlog (not to implement them).
---

# Adding features to `harness/feature_list.json`

Registers new tasks in the agent harness backlog. It does **not implement** the
features: it only plans them and adds them in `"pending"` status so an agent picks
them up later (`one_feature_at_a_time` rule). One entry per implementation the user
states, unless they ask to group them.

## File and schema

`harness/feature_list.json` (repo root). Array `features` of flat objects with
**exactly** these fields (2-space indentation). Closed tasks are NOT here: `close.sh`
moves them to `harness/feature_list_archive.json` (same schema, only
`done`/`Cancelled`); ids are **global** across both files:

```jsonc
{
  "id": 32,                       // integer, sequential = (current max id) + 1, +1 per feature
  "name": "ui_page_something",    // snake_case, area prefix (see conventions)
  "title": "Short descriptive title",
  "description": "What and why. Reference concrete files/functions. For bugs, paste the traceback. ALWAYS end with a line 'E2E verification: yes — <pages to walk>' or 'E2E verification: no — <reason>' (see conventions).",
  "acceptance": [                 // verifiable AND self-checkable criteria (see conventions)
    "tests/test_storage.py covers that save_config persists the new key (pytest tests/test_storage.py -k config)",
    "UI: on the affected page, the button shows 'Save' — verifiable with the verify skill"
  ],
  "status": "pending"             // ALWAYS pending on creation (never in_progress)
}
```

Do not add extra fields (there is no `priority`, `dependencies`, `category`...).
Dependencies are explained in prose inside `description`.

## Conventions

- **`id`**: sequential, never reused or renumbered. The next one = max across
  `feature_list.json` **and** `feature_list_archive.json` + 1.
- **`name`** (snake_case, in English) by area prefix:
  - `core_*` → core (`core/…`)  ·  `ui_*` → UI (`ui/…`)
  - `harness_*` → development infrastructure (`harness/…`)
  - `BUG_*` → bug. **To register a bug use the `add-bug` skill** (it applies the
    `BUG_` prefix and prioritizes it in `AGENTS.md`); do not register bugs from here.
  - refactor → verb (`reorganize_…`, `deduplicate_…`)
  - The list is not closed: if a new area appears, use a short prefix consistent with these.
- **Language**: everything in English — `title`/`description`/`acceptance`, code
  names, keys and files.
- **`acceptance`**: specific, verifiable and **self-checkable**: each criterion must
  state HOW it is checked, not only what must hold, so an agent can verify it without
  human intervention (e.g. as the exit condition of a `/goal` loop). Three valid forms:
  - a concrete test with its command (`pytest tests/test_X.py -k case`);
  - a command/script whose expected output is stated;
  - an observable UI step, prefixed `UI:`, describing page/action/result —
    verifiable with the `verify` skill (starts the real app and walks the flow).
  Avoid vague criteria ("works well") and criteria without a verification method.
- **E2E verification (`verify` skill)**: the last line of `description` declares
  whether the task requires E2E verification with the real app on close (it is the
  most token-expensive skill in the harness; it only runs right before
  `./harness/close.sh` or on explicit user request, never in the init):
  - `E2E verification: yes — <pages/tabs to walk>` when the feature adds or changes
    a UI flow, a computation the UI displays, or touches `core/` with visible impact
    on some page.
  - `E2E verification: no — <reason>` for small changes with no new UI flow:
    only `harness/`/`tests/`/docs, internal refactors with no behavior change,
    trivial style/text tweaks covered by a test.
  When in doubt, `yes`. If it is `no`, the `acceptance` criteria must not include
  `UI:` steps (they would be incoherent).
- **`status`** ∈ `pending | in_progress | done | blocked | Postponed | Cancelled`. On creation: **always `pending`**.

## Workflow

1. **Understand the request.** If the user lists several implementations, usually = one feature per item.
2. **Read the pending backlog** (not only the current code):
   ```bash
   python3 -c "
   import json
   for f in json.load(open('harness/feature_list.json'))['features']:
       if f['status'] == 'pending': print(f['id'], f['name'], '·', f['title'])
   "
   ```
   With two goals:
   - **Avoid duplicates**: if a `pending` task already covers (fully or partially)
     what is asked, tell the user instead of duplicating it.
   - **Use them as design context**: if a `pending` task is going to change the
     structure or behavior of the affected area (data schema, folder/UI layout,
     signature or location of a function…), write the new feature **accounting for
     that future change**, not only against today's code, and make the relation
     explicit in `description` (e.g. "assumes #NN will already have split page X in
     two sections"). Read the full `description` of the pending tasks touching the
     same area, not just the title.
3. **Design decisions first.** If a feature implies a non-trivial choice (where to
   store data, UI behavior, data source, scope...), use **AskUserQuestion BEFORE
   writing**, offering a recommendation as the first option. Do not invent the approach.
4. **Explore just enough.** To reference files/functions correctly in
   `description`/`acceptance`, consult the **"Module map"** of
   `harness/docs/architecture.md` (data schemas are in `harness/docs/data-models.md`)
   and, if precision is needed, read the concrete file (a `ui/` or `core/` module).
   Do not re-explore the whole repo for clear tasks.
5. **Compute the next id** (do not assume, and do it **right before writing**:
   another session or parallel job may have added entries since you opened the file):
   ```bash
   python3 -c "
   import json
   mx = 0
   for p in ('harness/feature_list.json', 'harness/feature_list_archive.json'):
       try:
           mx = max([mx] + [f['id'] for f in json.load(open(p))['features']])
       except FileNotFoundError:
           pass
   print(mx + 1)
   "
   ```
6. **Write and add** the entries right before the closing `]` of the `features`
   array, with consecutive ids, `status: "pending"`, respecting the schema/indentation.
7. **Validate** (see below).
8. **Summarize** to the user the `id · name · title` table. Do **not** commit unless
   asked; do **not** mark `in_progress`; do **not** implement the feature.

## Verification

```bash
python3 -c "
import json
d = json.load(open('harness/feature_list.json'))           # parses without error
fs = d['features']; valid = set(d['rules']['valid_status'])
try:
    arch = json.load(open('harness/feature_list_archive.json'))['features']
except FileNotFoundError:
    arch = []
ids = [f['id'] for f in fs] + [f['id'] for f in arch]
assert len(ids) == len(set(ids)), 'duplicated ids (archive included)'
for f in fs:
    assert f['status'] in valid, f'invalid status in {f[\"id\"]}'
    assert set(f) == {'id','name','title','description','acceptance','status'}, f'odd fields in {f[\"id\"]}'
print('OK:', len(fs), 'active ·', len(arch), 'archived')
"
git diff harness/feature_list.json   # only entries added before the final ]; rest intact
```

## What NOT to do

- Do not mark `done`/`in_progress` or implement the feature's code.
- Do not commit or push unless explicitly asked.
- Do not add fields outside the schema or change the `rules`.
- Do not touch existing entries (immutable ids).
