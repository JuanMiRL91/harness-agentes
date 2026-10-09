---
name: add-bug
description: Register a new bug in the project's harness backlog (harness/feature_list.json), in "pending" status and with the BUG_ name prefix so the agent picks it up BEFORE the features. Use it when the user reports an error, a failure, a traceback or incorrect behavior, to note it down (not to fix it on the spot).
---

# Registering a bug

Same as `/add-feature` (same schema, id computation and validation: read it), with these
differences:

- `name` **always** starts with `BUG_` (that is what prioritizes it over features).
- `description`: symptom, full traceback if any, file/function, how to reproduce and on
  which machine/OS if it may depend on it. If another `pending` task is going to rewrite
  that code, say so.
- Default `acceptance`: *test that reproduces the failure (fails before the fix) → fix at
  the root cause → test green + the existing ones of the area*, with exact commands. A
  `UI:` criterion only if the symptom is on screen.
- Do not fix the bug in this flow; do not commit.
