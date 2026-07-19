---
name: add-bug
description: Register a new bug in the harness backlog (harness/feature_list.json) of the project, in "pending" status and with the BUG_ name prefix so the agent picks it up BEFORE the features. Use it when the user reports an error, a failure, a traceback or incorrect behavior, to note it down (not to fix it on the spot).
---

# Adding a bug to `harness/feature_list.json`

Registers a **bug** in the same backlog as the features, but marking it with the
`BUG_` prefix in `name`. That prefix is what makes the agent reading `AGENTS.md`
take it **before** any `pending` feature (see §4 of `AGENTS.md`). It does **not fix**
the bug: it only registers it in `"pending"` status.

To register normal features use the sibling skill `add-feature`. This skill shares
its schema and conventions; only the `BUG_` prefix and the `acceptance` template differ.

## File and schema

`harness/feature_list.json` (repo root). Array `features` of flat objects with
**exactly** these fields (2-space indentation), same as a feature. Closed tasks are
NOT here: `close.sh` moves them to `harness/feature_list_archive.json` (same schema,
only `done`/`Cancelled`); ids are **global** across both files:

```jsonc
{
  "id": 34,                          // integer, sequential = (current max id) + 1
  "name": "BUG_empty_quote",         // ALWAYS BUG_ prefix + snake_case slug
  "title": "Short title of what fails",
  "description": "Symptom + full traceback + file/function where it happens + how to reproduce. ALWAYS end with a line 'E2E verification: yes — <pages to walk>' or 'E2E verification: no — <reason>' (see conventions).",
  "acceptance": [
    "Reproduce the error and locate the cause in <file>",
    "Fix the bug — checkable with <command or concrete UI step that previously failed>",
    "tests/test_X.py covers the case so it does not happen again (pytest tests/test_X.py -k case)"
  ],
  "status": "pending"                // ALWAYS pending on creation
}
```

Do not add extra fields (no `priority`, `type`, `category`…). The "bug type" is
encoded **only** with the `BUG_` prefix in `name`. Do not change the `rules`.

## Conventions

- **`name`**: **always** starts with `BUG_`, followed by a short, descriptive
  `snake_case` slug in English (`BUG_empty_quote`, `BUG_duplicate_key_page`). The
  prefix is mandatory: it is the marker that prioritizes the bug.
- **`id`**: sequential, never reused or renumbered. The next one = max across
  `feature_list.json` **and** `feature_list_archive.json` + 1.
- **`description`**: paste the **full traceback** if there is one, state the
  file/function and the steps to reproduce (which screen/action triggers it). The
  more concrete, the better. If the bug may depend on the system (encoding, paths,
  `python` vs `python3`…), note which machine it happened on if the project runs on
  several: there are OS-specific bugs.
- **`acceptance`**: by default follows the *reproduce → fix → regression test*
  pattern. Adjust the test name to the affected area (`tests/test_<module>.py`).
  Each criterion must be **self-checkable**: state the exact test command, or — if
  the symptom is UI — the observable step prefixed `UI:` (page/action/expected
  result), verifiable with the `verify` skill. That way the agent can close the bug
  as the exit condition of a `/goal` loop without human intervention.
- **E2E verification (`verify` skill)**: the last line of `description` declares
  whether the fix requires E2E verification with the real app on close (it only runs
  right before `./harness/close.sh` or on explicit user request, never in the init):
  - `E2E verification: yes — <pages/tabs to walk>` if the symptom is UI or the fix
    touches `core/` with visible impact on some page (the usual case for bugs).
  - `E2E verification: no — <reason>` for small fixes with no UI symptom: only
    `harness/`/`tests/`/docs, or a `core/` failure fully covered by the regression
    test with no observable effect on screen.
  When in doubt, `yes`. If it is `no`, the `acceptance` criteria must not include
  `UI:` steps (they would be incoherent).
- **Language**: everything in English — `title`/`description`/`acceptance`, code
  names, keys and files.
- **`status`**: on creation, **always `pending`**.

## Workflow

1. **Understand the bug.** Identify symptom, traceback, file/function and
   reproduction. If the user pastes a framework/Python error, keep it whole in
   `description`.
2. **Read the pending backlog** (not only the current code):
   ```bash
   python3 -c "
   import json
   for f in json.load(open('harness/feature_list.json'))['features']:
       if f['status'] == 'pending': print(f['id'], f['name'], '·', f['title'])
   "
   ```
   With two goals:
   - **Avoid duplicates**: if a pending `BUG_*` already registers the same symptom,
     tell the user instead of duplicating it.
   - **Use them as context**: if a `pending` task (bug or feature) is going to
     rewrite or restructure the code where the failure happens, make the relation
     explicit in `description` (e.g. "the affected code is rewritten by #NN; check
     whether the fix still applies afterwards") and adjust `acceptance` to how that
     code will end up, not only how it is today. Read the full `description` of the
     pending tasks touching the same area.
3. **Explore just enough.** To reference the file/function correctly, look at the
   "Module map" of `harness/docs/architecture.md` (data schemas in
   `harness/docs/data-models.md`); read the concrete file only if precision is
   needed. Do not re-explore the repo.
4. **Compute the next id** (do not assume, and do it **right before writing**:
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
5. **Write and add** the entry right before the closing `]` of the `features` array,
   with a `name` starting with `BUG_`, consecutive id, `status: "pending"` and the
   file's indentation.
6. **Validate** (see below).
7. **Summarize** to the user the created entry (`id · name · title`) and remind them
   that, when reading `AGENTS.md`, the agent will take this bug before the pending
   features. Do **not** commit unless asked; do **not** mark `in_progress`; do
   **not** fix the bug.

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
new = max(fs, key=lambda f: f['id'])
assert new['name'].upper().startswith('BUG'), 'the new bug must start with BUG_'
print('OK:', len(fs), 'active ·', len(arch), 'archived; last bug:', new['name'])
"
git diff harness/feature_list.json   # only the entry added before the final ]; rest intact
```

## What NOT to do

- Do not omit the `BUG_` prefix (without it, the bug is not prioritized).
- Do not mark `done`/`in_progress` or fix the code in this flow.
- Do not commit or push unless explicitly asked.
- Do not add fields outside the schema (no `type`/`category`/`priority`) or change the `rules`.
- Do not touch existing entries (immutable ids).
