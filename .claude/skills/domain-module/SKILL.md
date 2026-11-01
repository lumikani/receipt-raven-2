---
name: domain-module
description: Recipe for adding a backend domain module (aggregate, use cases, repository, router) across the DDD layers. Use when adding a new entity, aggregate or feature area to the backend.
---

# Adding a domain module

Follow `.agents/docs/domain-modules.md` step by step. The `notes` module is the
reference implementation: mirror its file layout and naming.

Before finishing:

1. `make lint`: ruff, pyright and import-linter all pass, and the new module is in
   the `domain-module-independence` contract in `backend/pyproject.toml`.
2. `make api-client` if any endpoint changed; commit `backend/openapi.json` and
   `frontend/src/api/generated/` with the change.
3. `make test-backend`: new API tests pass (load the `writing-tests` skill first).
4. The migration under `backend/alembic/versions/` matches the ORM model.
