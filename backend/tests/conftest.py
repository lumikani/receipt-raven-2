"""Pytest configuration and fixtures.

API tests run the real stack (HTTP client -> router -> use case -> repository)
against an in-memory SQLite database, created fresh for every test. The two
external services, the ledger and the AI model, are replaced by the fakes in
`tests/fakes.py`; uploaded documents go to a per-test temporary directory.
"""

import os
import tempfile

# Settings are read at import time in src.main, so the environment must be set
# before any src.* import below.
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JOB_WORKER_ENABLED"] = "false"
os.environ["AI_PROVIDER"] = "mock"
os.environ["AI_MOCK_DELAY_SECONDS"] = "0"
os.environ["UPLOADS_DIR"] = tempfile.mkdtemp(prefix="receipt-raven-uploads-")
os.environ["PAYEE_ACCOUNT_RULES_PATH"] = "/nonexistent/payee-account-rules.json"
os.environ["ACCOUNT_ROLES_PATH"] = "/nonexistent/account-roles.json"

from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from pathlib import Path

import pytest
from dependency_injector import providers
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.containers import container
from src.database import bind_db_session, get_db
from src.domain.jobs.entities.receipt_job import ReceiptJob
from src.infrastructure.jobs.storage.local_document_storage import LocalDocumentStorage
from src.main import app
from src.models import Base
from tests.fakes import FakeAccountRoles, FakeLedger, FakeReceiptAnalyzer


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """A session on a fresh in-memory database with every table created."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def ledger() -> Generator[FakeLedger]:
    """The ledger every use case talks to during the test."""
    fake = FakeLedger()
    with container.shared.ledger_service.override(providers.Object(fake)):
        yield fake


@pytest.fixture
def account_roles() -> Generator[FakeAccountRoles]:
    """The source-account roles every use case sees during the test."""
    fake = FakeAccountRoles()
    with container.shared.account_roles.override(providers.Object(fake)):
        yield fake


@pytest.fixture
def analyzer() -> Generator[FakeReceiptAnalyzer]:
    """The AI model the analysis worker asks during the test."""
    fake = FakeReceiptAnalyzer()
    with container.shared.receipt_analyzer.override(providers.Object(fake)):
        yield fake


@pytest.fixture
def uploads_dir(tmp_path: Path) -> Generator[Path]:
    """Where uploaded documents are stored during the test."""
    directory = tmp_path / "uploads"
    with container.shared.document_storage.override(
        providers.Object(LocalDocumentStorage(directory))
    ):
        yield directory


@pytest.fixture
async def client(
    db_session: AsyncSession,
    ledger: FakeLedger,
    account_roles: FakeAccountRoles,
    analyzer: FakeReceiptAnalyzer,
    uploads_dir: Path,
) -> AsyncGenerator[AsyncClient]:
    """An HTTP client for the app, bound to the test database and the fakes."""

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def run_worker(db_session: AsyncSession) -> Callable[[], Awaitable[ReceiptJob | None]]:
    """Run one iteration of the analysis worker, as the background task would."""

    async def run() -> ReceiptJob | None:
        with bind_db_session(db_session):
            use_case = container.analysis.process_next_job_use_case()
        return await use_case.process_next_job()

    return run
