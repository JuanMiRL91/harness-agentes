# Session history

> **Append-only** log: only `harness/close.sh` writes here, archiving `current.md`
> when each session closes. Do not edit by hand. Read it with `grep`, never whole.
>
> Above 200 KB, `harness/rotate_history.py` moves the oldest entries
> to `archive/` until it is under 100 KB (immutable files).
