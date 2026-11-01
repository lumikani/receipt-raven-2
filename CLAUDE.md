# AGENTS.md

## About this repo

Receipt Raven: turns receipt photos into Beancount ledger transactions. FastAPI +
SQLAlchemy + SQLite backend, Vite + React + TanStack Router + Tailwind/shadcn/ui
frontend, one Docker image serving both. `beancount-service/` is a separate small
FastAPI service that owns the ledger file; the backend talks to it over HTTP
(`src/infrastructure/ledger/beancount_ledger_service.py`). Generated from a Copier
template (Postgres replaced by SQLite); `make template-update` pulls template changes.

`AGENTS.md` is a symlink to `CLAUDE.md`; both names load this file. Agent-facing
documentation lives under `.agents/`.

## Agent skills

### Issue tracker

Issues and scratch tickets live as local markdown files under `.agents/scratch/`. See `.agents/docs/issue-tracker.md`.

### Domain docs

Single-context: `GLOSSARY.md` at the repo root (created lazily) and ADRs in `.agents/docs/adr/`. See `.agents/docs/domain.md`.

## Links

- `.agents/docs/` — ways of working: commands, architecture, API contract, frontend, testing, working style
- `.agents/docs/issue-tracker.md` — where issues live (local markdown under `.agents/scratch/`)
- `.agents/docs/domain.md` — how to consume `GLOSSARY.md` and the ADRs
- `.agents/docs/domain-modules.md` — recipe for adding a backend domain module
- `.agents/docs/adr/` — architecture decision records
- `.agents/scratch/` — scratch space and local issue files (gitignored)
- `README.md` — human-facing project overview
