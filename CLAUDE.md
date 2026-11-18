# AGENTS.md

## About this repo

Receipt Raven turns receipt photos into Beancount ledger transactions: a FastAPI +
SQLAlchemy + SQLite backend and a Vite + React + TanStack Router + Tailwind frontend
served from one Docker image, with `beancount-service/` owning the ledger file over
HTTP. Generated from a Copier template (Postgres replaced by SQLite); `make
template-update` pulls template changes.

## Commands

`make help` lists everything. The ones you will need:

| Task | Command |
|---|---|
| Everything CI checks | `make check` |
| Backend lint (ruff, pyright, import-linter) | `make lint` |
| Frontend lint (prettier, oxlint, tsc, knip, dependency-cruiser) | `make lint-frontend` |
| All tests | `make test` |
| Backend tests | `make test-backend` |
| Beancount service tests | `make test-beancount` |
| Frontend tests | `make test-frontend` |
| Duplication check (jscpd) | `make duplication-check` |
| After any backend API change | `make api-client` |
| New migration from model changes | `make migrate-new msg="..."` |

## Working style

- Do not redesign the architecture or create broader plans unless asked.
- On bigger tasks, make small, logically separated commits.
- Write commit messages in imperative mood, preferably under 60 characters, 80 at
  most, and free of references to wayfinder tickets.
- The pre-commit hook (husky + lint-staged) formats and lints staged files.

## Links

- `.agents/` — documentation for agents and development efforts (specs and tickets live under `.agents/scratch/`). Intentionally untracked (gitignored): local-only, never commit it.
- `.agents/docs/GLOSSARY.md` - canonical domain terms; use them in code, tickets and docs.
- `.agents/docs/issue-tracker.md` - where issues, specs and tickets live, and their conventions.
- `.agents/docs/architecture.md` - backend DDD/hexagonal rules, module layout, read models; read before changing `backend/src/`.
- `.agents/docs/api-contract.md` - the committed OpenAPI contract and the generated frontend client; read after any backend API change.
- `.agents/docs/frontend.md` - frontend conventions (lint, routes, module boundaries, UI, tests); read before changing `frontend/src/`.
- `.agents/docs/testing.md` - test policy, type checking, duplication ratchet; read before writing tests or changing checks.
- `.agents/docs/local-ocr-models.md` and `.agents/docs/local-ocr-analysis.md` - facts about the local OCR provider and the analysis pipeline.
- `docs/agents/domain-modules.md` - recipe for adding a backend domain module (`receipts` is the reference); use with the `domain-module` skill.
- `docs/adr/` - architecture decision records.
