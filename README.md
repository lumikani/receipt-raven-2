# Receipt Raven

Take a photo of a receipt; an AI model reads the payee, date, items and total;
you check and correct it; approving books it as a transaction to your Beancount
ledger.

| Part | Stack |
|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy 2 (async), Alembic, SQLite, dependency-injector |
| Ledger service | `beancount-service/`: FastAPI + beancount, owns the ledger file |
| Frontend | Vite, React 19, TanStack Router + Query, Tailwind CSS v4 + shadcn/ui, installable PWA |
| AI | OpenRouter (default) or OpenAI, any vision model; a mock provider for development |
| Packaging | One Docker image for the app (FastAPI serves the API and the built frontend), one for the ledger service |

## Features

- Upload a photo or PDF (camera, file picker, drag and drop, or the phone's share sheet)
- Analysis queue with automatic retries and a manual retry for failed uploads
- Review screen: the document next to an editable form, a warning when the
  read date looks wrong, payee and account suggestions from the ledger
- Item tools: merge items, assign the gap between items and total to one item
- Approval writes the transaction to the ledger, items merged per expense account
- Receipts entered by hand, without a document
- Payee rules that choose the paying account (`backend/config/payee-account-rules.example.json`)
- Disk budget for uploaded documents (`MAX_UPLOADS_DISK_SIZE`)

## Requirements

- [uv](https://docs.astral.sh/uv/) (installs Python 3.13 for you)
- Node.js 24 (`nvm use` reads `.nvmrc`)
- Docker, for the production images

## Getting started

```bash
make install        # backend, beancount-service and frontend dependencies
cp .env.example .env  # AI_PROVIDER=mock works without an API key
make migrate        # create the SQLite database in backend/data/
make dev-ledger     # beancount service on :8100, on a copy of dev-ledger/
make dev-app        # backend on http://localhost:8000 (API docs at /api/v1/docs)
make dev-frontend   # frontend on http://localhost:5173, proxies /api to :8000
```

To read real receipts, set `AI_PROVIDER=openrouter` and `OPENROUTER_API_KEY` in
`.env`. If port 8000 is taken, run the backend elsewhere and start the frontend
with `API_PROXY_TARGET=http://localhost:<port>`.

## Local OCR + hledger setup (run on the host)

A personal-finance setup that runs everything locally on the host — no Docker,
no cloud AI. Requirements: [ollama](https://ollama.com) with the OCR model
pulled (`ollama pull richardyoung/lightonocr-3-4b:Q4_K_M`) listening on
`localhost:11434`, and the `hledger` CLI installed.

```bash
cp .env.example .env        # then edit .env (use absolute paths — `~` is not expanded):
#   AI_PROVIDER=local
#   LOCAL_BASE_URL=http://localhost:11434/v1
#   LOCAL_MODEL=richardyoung/lightonocr-3-4b:Q4_K_M
#   LEDGER_PROVIDER=hledger
#   HLEDGER_FILE=/home/you/.ledger/current.journal        # reads + validation
#   HLEDGER_APPEND_FILE=/home/you/.ledger/receipts.journal  # app-owned append target,
#                                                           # included from the main journal
cp backend/config/account-roles.example.json backend/config/account-roles.json
# then edit backend/config/account-roles.json: set the real last four digits of
# each card in "cardLastDigits" (the digits printed on the receipt's `Kortti:`
# line). The card that paid then picks the receipt's source account automatically.
make migrate
make dev-app        # backend on http://localhost:8000
make dev-frontend   # frontend on http://localhost:5173
```

With `AI_PROVIDER=local` only image photos are supported (JPEG/PNG) — upload a
PDF and the analysis fails with a clear message; cloud providers keep PDF
support. The beancount backend stays available behind the switch:
`LEDGER_PROVIDER=beancount` (default) plus `make dev-ledger`.

## Running in production

```bash
LEDGER_DIR=/path/to/ledger-directory make docker-up
```

`docker-compose.yml` runs both images. `LEDGER_DIR` must contain
`ledger.beancount`; approved receipts are appended to it. The database and
uploads live in Docker volumes. Put the AI settings in `.env`.

## Everyday commands

| Command | What it does |
|---|---|
| `make check` | Everything CI runs: lint, types, architecture contracts, dependency rules, duplication, tests |
| `make test` | Backend and beancount-service (pytest) and frontend (Vitest in Chromium) tests |
| `make api-client` | Re-export `backend/openapi.json` and regenerate `frontend/src/api/generated/` |
| `make migrate-new msg="..."` | Create an Alembic migration from model changes |
| `make deps-graph` | Print the frontend module graph as Mermaid |
| `make docker-up` | Build both images and run them on http://localhost:8000 |
| `make template-update` | Pull the latest project template (`copier update`) |

The first time you run the frontend tests, install the browser:
`cd frontend && npx playwright install chromium`.

## How the API client is generated

1. FastAPI routes define the API. Handler names become OpenAPI operationIds.
2. `backend/scripts/export_openapi.py` writes `backend/openapi.json` without a
   running server.
3. orval (`frontend/orval.config.ts`) generates TanStack Query hooks and
   TypeScript models into `frontend/src/api/generated/`, calling the backend
   through `frontend/src/api/axios-instance.ts`.

Both outputs are committed. CI regenerates them and fails on any difference, so
an API change and its frontend impact land in the same pull request.

## Architecture

The backend follows Domain-Driven Design with hexagonal (ports and adapters)
boundaries:

```
backend/src/
  domain/          entities, value objects, rules: no framework imports
  application/     use cases (commands/, queries/) and ports (protocols/)
  infrastructure/  ORM, repositories, query adapters, routers, schemas
  containers/      dependency-injector wiring
```

import-linter enforces the layer rules (`backend/pyproject.toml`). The frontend's
module rules live in `frontend/.dependency-cruiser.cjs`. See `CLAUDE.md` for the
full rules, `docs/agents/domain-modules.md` for adding a module, and
`docs/adr/` for the decisions behind them.

## Quality tooling

| Tool | Checks | Where configured |
|---|---|---|
| ruff | Python lint and format | `backend/pyproject.toml` |
| pyright (strict) | Python types | `backend/pyproject.toml` |
| import-linter | Backend layer and module boundaries | `backend/pyproject.toml` |
| oxlint (type-aware, via tsgolint) | TypeScript lint | `frontend/.oxlintrc.json` |
| Prettier | TypeScript formatting | `frontend/.prettierrc` |
| tsc (TypeScript 7) | TypeScript types | `frontend/tsconfig.json` |
| knip | Unused files, exports and dependencies | `frontend/knip.config.ts` |
| dependency-cruiser | Frontend module boundaries, cycles | `frontend/.dependency-cruiser.cjs` |
| jscpd | Copy-paste duplication (ratchet threshold) | `backend/.jscpd.json`, `frontend/.jscpd.json` |
| husky + lint-staged | Format and lint staged files on commit | `package.json` |
| Claude Code hooks | Same checks at the end of each agent turn | `.claude/settings.json` |
