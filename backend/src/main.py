"""FastAPI application entry point."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import configure_logging, get_settings
from src.containers import container
from src.database import dispose_engine, get_session_factory, initialize_database
from src.infrastructure.analysis.job_worker import JobWorker
from src.infrastructure.classification.routers import classification as classification_router
from src.infrastructure.common.error_handlers import register_error_handlers
from src.infrastructure.common.middleware import (
    RequestIdAndLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from src.infrastructure.common.openapi import operation_id
from src.infrastructure.common.spa import mount_spa
from src.infrastructure.jobs.routers import jobs as jobs_router
from src.infrastructure.jobs.storage.cleanup_scheduler import run_cleanup_schedule
from src.infrastructure.ledger.routers import ledger as ledger_router
from src.infrastructure.receipts.routers import receipts as receipts_router

settings = get_settings()
configure_logging(settings)
logger = structlog.get_logger(__name__)

# The Docker image copies the frontend build here; absent in development.
STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Start the database and the background tasks; stop them on shutdown."""
    initialize_database(settings)
    tasks = [
        asyncio.create_task(
            run_cleanup_schedule(
                container.shared.uploads_cleanup(), settings.CLEANUP_INTERVAL_HOURS
            )
        )
    ]
    if settings.JOB_WORKER_ENABLED:
        worker = JobWorker(
            session_factory=get_session_factory(settings),
            use_case_provider=container.analysis.process_next_job_use_case,
            poll_interval_seconds=settings.JOB_POLL_INTERVAL_SECONDS,
        )
        tasks.append(asyncio.create_task(worker.run_forever()))
    logger.info(
        "app_started",
        environment=settings.ENVIRONMENT,
        version=settings.VERSION,
        ai_provider=settings.AI_PROVIDER,
    )
    yield
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await dispose_engine()


_docs_enabled = settings.ENVIRONMENT != "production"

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url=f"{settings.API_V1_PREFIX}/docs" if _docs_enabled else None,
    redoc_url=None,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if _docs_enabled else None,
    lifespan=lifespan,
    generate_unique_id_function=operation_id,
)

app.add_middleware(RequestIdAndLoggingMiddleware, api_prefix=settings.API_V1_PREFIX)
app.add_middleware(SecurityHeadersMiddleware, production=settings.ENVIRONMENT == "production")
# With wildcard origins, browsers reject credentials, so only allow them otherwise.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials="*" not in settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """Liveness probe for Docker and load balancers."""
    return {"status": "healthy"}


# Routers, one block per module
app.include_router(receipts_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(jobs_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(ledger_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(classification_router.router, prefix=settings.API_V1_PREFIX)

# Last: its catch-all route would otherwise shadow the API.
mount_spa(app, STATIC_DIR, settings.API_V1_PREFIX)
