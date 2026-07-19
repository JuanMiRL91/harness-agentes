# Architecture

> **Template** — this document is the source of **fine detail** for the project: it is
> filled in and maintained while implementing. `harness/check_docs.py` cross-checks
> the public symbols of each session's diff against this file (and `data-models.md` /
> `CLAUDE.md`): every new public function must end up mentioned here.

## Architecture decisions (closed)

_List of decisions taken and closed, with their rationale in one or two lines.
Examples: chosen stack, persistence, external data sources, what is out of scope.
Open decisions do NOT go here: they go to the backlog or to ideas._

- ...

## Module map

_One section per `core/` and `ui/` module, with its public functions: brief signature,
what it does, what it raises. This is the level of detail that does NOT go in
`CLAUDE.md` (there, only the one-line map per module)._

### core/<module>.py

- `public_function(arg) -> type` — what it does, invariants, exceptions.

### ui/<page>.py

- ...

## Findings verified live

_Behaviors of external APIs, data series, limits or quirks verified empirically
during development. Avoids re-discovering them every session._

- ...
