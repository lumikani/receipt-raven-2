# ADR-0001: Read models and query services (CQRS-lite)

- **Status:** Accepted
- **Applies to:** `backend/`

## Context

The backend is a DDD modular monolith: modules under `src/domain`,
`src/application` and `src/infrastructure`, with strict domain-module
independence enforced by import-linter.

If repositories serve both jobs, managing aggregate lifecycle (load, mutate,
save) *and* feeding views, view-shaped data gets squeezed through
aggregate-shaped interfaces. Repositories grow methods that return tuples of
several aggregates, and pages load whole aggregates only to throw most of each
away. The cost is paid twice: at runtime (aggregates hydrated to be discarded)
and in the design (aggregate boundaries blur to serve rendering).

## Decision

**Reads and writes get separate models.** The write side is router → command
use case → aggregate → repository. The read side uses **query services**:
purpose-built view DTOs served by dedicated ports whose adapters map ORM rows
directly to those DTOs.

| Where | What |
|---|---|
| `src/application/<module>/queries/` | Frozen view-DTO dataclasses, the query protocol (port), and the read use case that wraps it |
| `src/application/<module>/commands/` | Commands only |
| `src/infrastructure/<module>/queries/` | The query adapter. Like repositories, it may import ORM models, and it maps rows straight to view DTOs |

**Routers always call use cases, reads included.** A read use case is a thin
wrapper around the query port. The wrapper is deliberate boilerplate: one rule
with no exceptions ("routers call use cases") is easier to follow and review.

**Rule 1: queries never decide.** A query adapter returns data; business rules
stay in the domain. If a read needs a rule, the use case applies it, or the
adapter reuses a domain or application service rather than re-encoding the rule
in SQL.

**Rule 2: read models are dead ends.** View DTOs never flow into a command or
the domain. The `queries-are-dead-ends` import-linter contract forbids
`src.domain` and `src.application.*.commands` from importing
`src.application.*.queries`. A read use case may call a command use case
(the reverse direction).

**The halfway option.** A read too small to deserve its own port still lives in
`queries/`, but delegates to the repository and returns domain entities
(`GetNoteUseCase`). Promote it to a port when it starts to need view-shaped data.

## Consequences

- Each new view adds a DTO, a port, an adapter and a use case. That is more
  files, each of them simple.
- Aggregates and repositories stay shaped by invariants, not by pages.
- Reference implementation: the receipt list (`ListReceiptsUseCase`,
  `ReceiptListQueryProtocol`, `ReceiptListQuery`).
