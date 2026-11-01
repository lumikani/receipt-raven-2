# Adding a domain module

A module is one feature area (for example `projects` or `billing`) spread over
the three layers. The `receipts` module is the reference implementation; every path
below has a `receipts` counterpart to copy from. Replace `<module>`, `<Entity>` and
`<entity>` throughout.

## 1. Domain (`backend/src/domain/`)

| File | What goes in it |
|---|---|
| `common/value_objects/ids.py` | `<Entity>Id(EntityId)` with `value: int`; export it from `common/value_objects/__init__.py` |
| `<module>/entities/<entity>.py` | The aggregate: a `@dataclass` subclassing `AggregateRoot[<Entity>Id]`. Invariants are checked in `__post_init__` and in every mutating method. Provide `create(...)` (id `0`) and `create_with_id(...)` (reconstitution) |
| `<module>/exceptions.py` | `<Entity>NotFoundError(EntityNotFoundError)` and any rule-specific errors |

The domain imports only `src.domain.common` and itself: no SQLAlchemy, no
FastAPI, no Pydantic. Reference other modules' aggregates by id.

Add `"src.domain.<module>"` to the `domain-module-independence` contract in
`backend/pyproject.toml`.

## 2. Application (`backend/src/application/<module>/`)

| File | What goes in it |
|---|---|
| `protocols/<entity>_repository.py` | The repository port: a `Protocol` with the methods use cases need |
| `commands/<verb>_<entity>_use_case.py` | One class per command. Takes primitives, returns domain entities |
| `queries/<view>.py` | For list or composite views: frozen view-DTO dataclasses plus a `Protocol` query port |
| `queries/<verb>_<entity>_use_case.py` | One read use case per view. A small read may delegate to the repository instead of a port |

Commands never import from `queries/` (the `queries-are-dead-ends` contract).

## 3. Infrastructure (`backend/src/infrastructure/<module>/`)

| File | What goes in it |
|---|---|
| `orm/<entity>_model.py` | SQLAlchemy model on `src.database.Base`; register it in `src/models.py` |
| `mappers/<entity>_mapper.py` | `to_domain` / `to_orm`, using `orm_id()` for new entities |
| `repositories/<entity>_repository.py` | Subclass `BaseRepository[<Entity>, <Entity>Model]`; add only the queries the base lacks |
| `queries/<view>_query.py` | Query adapter: selects columns and builds view DTOs directly, no aggregates |
| `schemas/__init__.py` | Pydantic request/response models |
| `routers/<module>.py` | `APIRouter`; each handler resolves its use case with `inject_use_case(container.<module>.<use_case>)` and converts results to schemas. Handler names must be unique app-wide: they are the OpenAPI operationIds |

## 4. Wiring

1. `backend/src/containers/shared.py`: a `providers.Factory` for each repository
   and query adapter, built with `db=db`.
2. `backend/src/containers/<module>.py`: a `DeclarativeContainer` declaring its
   dependencies with `providers.Dependency()` and one `providers.Factory` per use case.
3. `backend/src/containers/root.py`: `<module> = providers.Container(<Module>Container, ...)`.
4. `backend/src/main.py`: `app.include_router(<module>_router.router, prefix=settings.API_V1_PREFIX)`.

## 5. Database migration

```bash
make migrate-new msg="create <entity> table"
```

Review the generated file in `backend/alembic/versions/`, then `make migrate`.

## 6. Tests and the API client

1. API tests in `backend/tests/test_<module>.py` (see the `writing-tests` skill).
2. Unit tests in `backend/tests/unit/domain/` only for invariants with real branching.
3. `make api-client`, then use the generated hooks from
   `frontend/src/api/generated/<tag>/<tag>.ts` in the frontend.
4. `make check`.
