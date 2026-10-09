# Architecture

> **Template** — decisions, invariants and verified findings: what the code does NOT say
> by itself. Not a function-by-function map (the code and its docstrings are). Keep it
> under 60,000 characters (`close.sh` enforces it): delete what stops being true.

## Architecture decisions (closed)

_Decisions taken and closed, with their rationale in one or two lines. Examples: chosen
stack, persistence, external data sources, what is out of scope. Open decisions do NOT
go here: they go to the backlog or to ideas._

- ...

## Invariants

_Rules the code must keep that a reader could break without noticing (single point of
truth for a computation, atomic writes, ids that never change…)._

- ...

## Findings verified live

_Behaviors of external APIs, data series, limits or quirks verified empirically during
development. Avoids re-discovering them every session._

- ...
