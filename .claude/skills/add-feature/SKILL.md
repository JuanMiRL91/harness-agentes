---
name: add-feature
description: Add one or several new tasks to the project's harness backlog (harness/feature_list.json), in "pending" status and following the repo conventions. Use it when the user asks to "add a feature/task", "new feature", or describes implementations to register in the backlog (not to implement them).
---

# Adding tasks to `harness/feature_list.json`

Registers `pending` tasks; it **does not implement them**. One entry per requested
implementation, unless the user asks to group them. For bugs, use `/add-bug`.

## Schema (exactly these fields, 2-space indentation)

```jsonc
{
  "id": 42,                   // max(id) across feature_list.json AND feature_list_archive.json + 1
  "name": "core_something",   // snake_case, area prefix: core_ ui_ harness_ …
  "title": "Short title",     // no «|»: close.sh uses it as a separator (use «·»)
  "description": "What and why, with concrete files/functions. Last line: 'E2E verification: yes — <pages>' or 'E2E verification: no — <reason>'.",
  "acceptance": ["criterion + how it is checked (pytest ... -k case | command | 'UI: page/action/result')"],
  "status": "pending"
}
```

## Writing rules — short specs

- A capable model implements it (usually the main chat model): describe **what** and
  **why**, the files involved and the hard constraints (private data, stable ids,
  compatibility). **Do not dictate the how** unless there is a single acceptable way.
  Target: `description` ≤ ~1,200 characters; if it needs much more, split the task or
  raise the decision with the user first.
- 2-5 `acceptance` criteria, each with its verification method. Nothing vague.
- `E2E verification` is only intent (which pages to walk if the user asks for
  `/verify`); if it is `no`, no `UI:` criteria.
- Non-trivial design choices → `AskUserQuestion` BEFORE writing, with the recommendation
  as the first option.
- Look at the `pending` tasks of the same area to avoid duplicates and to write
  accounting for them.

## Steps

```bash
# pending tasks (duplicates / context)
python3 -c "
import json
for f in json.load(open('harness/feature_list.json'))['features']:
    if f['status'] == 'pending': print(f['id'], f['name'], '·', f['title'])
"
# next id, right before writing
python3 -c "
import json
print(max([0] + [f['id'] for p in ('harness/feature_list.json','harness/feature_list_archive.json') for f in json.load(open(p))['features']]) + 1)
"
```

Append the entries at the end of the `features` array and validate:

```bash
python3 -c "
import json
d = json.load(open('harness/feature_list.json')); fs = d['features']
arch = json.load(open('harness/feature_list_archive.json'))['features']
ids = [f['id'] for f in fs + arch]; assert len(ids) == len(set(ids)), 'duplicated ids'
for f in fs:
    assert set(f) == {'id','name','title','description','acceptance','status'}, f['id']
    assert '|' not in f['name'] + f['title'], f\"{f['id']}: no '|' in name/title (close.sh)\"
print('OK', len(fs), 'active')
"
```

Summarize to the user `id · name · title`. Do not commit, do not mark `in_progress`, do
not touch existing entries.
