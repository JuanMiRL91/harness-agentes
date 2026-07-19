# Data models

> **Template** — complete schema of ALL the project's data files (JSON, YAML, CSV…).
> Every schema change (new, renamed or removed key, or changed semantics) is
> documented here **in the same session** that introduces it; `harness/check_docs.py`
> and `close.sh` verify it.

## Conventions

- Data keys in English; user-visible texts in the UI language.
- Atomic writes (temporary file + rename) for every JSON the app edits.
- No derived data persisted twice: if it can be computed, compute it.

## <file>.json

Path: `<where it lives>` · Written by: `<module>` · Read by: `<modules>`

```jsonc
{
  "key": "type and semantics",
  "other_key": 0
}
```

Notes: edge cases, null values, schema versioning if any.
