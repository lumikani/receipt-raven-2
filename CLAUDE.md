# Claude Code Project Guidelines

Receipt Raven: turns receipt photos into Beancount ledger transactions. FastAPI +
SQLAlchemy + SQLite backend, Vite + React + TanStack Router + Tailwind/shadcn/ui
frontend, one Docker image serving both. `beancount-service/` is a separate small
FastAPI service that owns the ledger file; the backend talks to it over HTTP
(`src/infrastructure/ledger/beancount_ledger_service.py`). Generated from a Copier
template (Postgres replaced by SQLite); `make template-update` pulls template changes.

## Commands

`make help` lists everything. The ones you will need:

| Task | Command |
|---|---|
| Everything CI checks | `make check` |
| Backend tests | `make test-backend` |
| Beancount service tests | `make test-beancount` |
| Frontend tests | `make test-frontend` |
| After any backend API change | `make api-client` |
| New migration from model changes | `make migrate-new msg="..."` |

## Type checking

The backend uses **pyright** in strict mode (not mypy). Run `cd backend && uv run pyright`
after changing Python files; never suggest or run mypy.

## Architecture: DDD with hexagonal boundaries

The backend layers under `backend/src/` are `domain/`, `application/` and
`infrastructure/`, wired by `containers/`. import-linter enforces the dependency
rules (contracts in `backend/pyproject.toml`, run by `make lint`, CI and a Stop
hook). What you can't infer from the code:

- **ORM models live only in infrastructure.** Repositories convert ORM ↔ domain.
  Routers convert domain entities ↔ Pydantic schemas; use cases return domain
  entities or view DTOs, never Pydantic.
- **Value objects → primitives before Pydantic**: `Receipt(id=receipt.id.value)`,
  never `Receipt(id=receipt.id)`.
- **`joinedload()` with collections needs `.unique()`** on the result.
- **Domain modules are strict, the application layer is relaxed**: a domain module
  imports only itself and `domain/common/`, and references other modules'
  aggregates by ID. Application use cases *may* import other modules' protocols
  and entities to compose read models.
- **Raise specific NotFound subclasses** (`ReceiptNotFoundError`), never
  `EntityNotFoundError("Receipt", id)`. Each module has its own `exceptions.py`.
- **Handler names are operationIds.** The generated frontend hooks are named
  after them (`list_receipts` → `useListReceipts`), so they must be unique app-wide.

Adding a module: load the `domain-module` skill (recipe in
`docs/agents/domain-modules.md`; `receipts` is the reference module).

### Modules

| Module | What it owns |
|---|---|
| `receipts` | Receipt aggregate with items; approval books it to the ledger |
| `jobs` | Uploaded documents queued for analysis, retries, stored files |
| `analysis` | Application/infrastructure only: the background worker (`JobWorker`) and AI analyzers |
| `ledger` | Accounts, payees and receipt transactions of the external ledger |

External services sit behind ports and are replaced in tests by the fakes in
`backend/tests/fakes.py` (container overrides in `tests/conftest.py`), never by
mocks. SQLite runs in WAL mode; Alembic migrations use batch mode.

### Read models (CQRS-lite)

A new read starts in `src/application/<module>/queries/` (view DTOs + query port
+ read use case; ORM-to-DTO adapter in `src/infrastructure/<module>/queries/`).
`commands/` holds commands only, and read DTOs must never reach a command:
the `queries-are-dead-ends` contract enforces it. A read too small to deserve a
port still lives in `queries/`, delegating to a repository and returning domain
entities. Decision and rationale: `docs/adr/0001-read-models-and-query-services.md`.

## API contract and generated client

`backend/openapi.json` is the committed API contract. `frontend/src/api/generated/`
is generated from it by orval (TanStack Query hooks + models). Never edit either
by hand: change the backend, run `make api-client`, commit both. CI fails when
either is stale.

## Frontend

- TypeScript 7. Lint is **oxlint** with type-aware rules (`npm run lint`,
  config in `.oxlintrc.json`), not ESLint: typescript-eslint does not support
  TypeScript 7. Never add ESLint or a second TypeScript version.
- Routes live in `src/routes/` (file-based, `tsr generate` builds
  `routeTree.gen.ts`); a file prefixed with `-` is ignored by the router.
- Module boundaries are enforced by dependency-cruiser
  (`frontend/.dependency-cruiser.cjs`): routes → components → hooks/lib → api.
  Only `src/api` talks HTTP; everything else uses the generated hooks.
  `make deps-graph` prints the graph.
- UI is Tailwind CSS v4 + shadcn/ui. Primitives live in `src/components/ui/`
  (add more with `npx shadcn@latest add <name>` from `frontend/`); theme tokens
  are CSS variables in `src/index.css`.
- Tests: a `.test.tsx` renders the whole app at a route through
  `renderApp` (`tests/harness/`) against MSW handlers (`tests/msw/`), in real
  Chromium. A request with no handler fails the test. Query by role and
  accessible name, not by CSS.

## Testing

Run the full test suite after any migration or refactoring; do not declare work
complete until it passes. Test policy (API-first tiering, assertion depth, when
unit tests are warranted): load the `writing-tests` skill before writing or
reviewing tests.

## Duplication (jscpd)

`make duplication-check` runs jscpd for both stacks; CI fails once duplicated
lines pass the `threshold` in `backend/.jscpd.json` or `frontend/.jscpd.json`.
The threshold is a **ratchet**: it may fall, never rise. When a refactor drops
the percentage, lower the threshold in the same commit; never raise it to make
the check pass. Extract the shared code instead. A Stop hook flags clones that
overlap lines the current turn changed.

## Working style

- Do not redesign the architecture or create broader plans unless asked.
- On bigger tasks, make small, logically separated commits.
- Write commit messages in imperative mood, keep them to preferably less than 60 characters, 80 at most.
- Commit messages should be free of references to wayfinder tickets.
- The pre-commit hook (husky + lint-staged) formats and lints staged files.
