"""Application configuration."""

import logging
import sys
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Literal

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).parent.parent.resolve()


def _read_project_version() -> str:
    """Read the release version from `pyproject.toml`.

    The Docker image copies the manifest next to `src/`, so the same file is the
    version source in development and in the container.
    """
    manifest = BACKEND_ROOT / "pyproject.toml"
    try:
        with manifest.open("rb") as handle:
            return str(tomllib.load(handle)["project"]["version"])
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        logging.getLogger(__name__).warning("Could not read version from %s", manifest)
        return "unknown"


def sqlite_file_path(url: str) -> Path | None:
    """Return the database file of a file-backed SQLite URL, or None (in-memory)."""
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return None
    path = url.removeprefix(prefix)
    if not path or path == ":memory:":
        return None
    return Path(path)


class Settings(BaseSettings):
    """Application settings, read from the environment and `.env`."""

    # env_ignore_empty: docker compose passes `${VAR:-}` as an empty string,
    # which must mean "unset", not an empty value.
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", env_ignore_empty=True
    )

    DATABASE_URL: str = (
        "postgresql://receipt_raven:receipt_raven_dev_password@localhost:5432/receipt_raven"
    )

    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Receipt Raven"
    VERSION: str = _read_project_version()

    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    LOG_LEVEL: str = "INFO"

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Uploaded receipt documents
    UPLOADS_DIR: Path = Path("./uploads")
    MAX_UPLOAD_SIZE_MB: float = 10
    # Disk budget for UPLOADS_DIR, such as "1GB" or "500MB". When exceeded, the
    # oldest documents are deleted. Unset: never clean up.
    MAX_UPLOADS_DISK_SIZE: str | None = None
    CLEANUP_INTERVAL_HOURS: float = 24

    # Receipt analysis
    AI_PROVIDER: Literal["openrouter", "openai", "mock", "local"] = "openrouter"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "anthropic/claude-haiku-4.5"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    # Local OCR provider: an ollama-compatible /v1 endpoint on the host
    LOCAL_BASE_URL: str = "http://localhost:11434/v1"
    LOCAL_MODEL: str = "richardyoung/lightonocr-3-4b:Q4_K_M"
    AI_TIMEOUT_SECONDS: float = 120
    # How long the mock provider pretends to think.
    AI_MOCK_DELAY_SECONDS: float = 3
    JOB_WORKER_ENABLED: bool = True
    JOB_POLL_INTERVAL_SECONDS: float = 1
    MAX_JOB_ATTEMPTS: int = 3
    # Source account for analysed receipts no payee rule matches.
    DEFAULT_SOURCE_ACCOUNT: str | None = None
    PAYEE_ACCOUNT_RULES_PATH: Path = Path("./config/payee-account-rules.json")
    # Expense account for receipt items no classification rule matches.
    DEFAULT_UNALLOCATED_ACCOUNT: str = "expenses:unallocated"
    # Source-account roles (personal cards vs shared card) for ledger/CSV
    # routing; copy config/account-roles.example.json and edit.
    ACCOUNT_ROLES_PATH: Path = Path("./config/account-roles.json")

    # Ledger: `beancount` (the beancount service over HTTP) or `hledger`
    # (a journal file plus the hledger CLI, no service process).
    LEDGER_PROVIDER: Literal["beancount", "hledger"] = "beancount"
    BEANCOUNT_SERVICE_URL: str = "http://localhost:8100"
    BEANCOUNT_TIMEOUT_SECONDS: float = 10
    # hledger backend. HLEDGER_FILE (reads + validation) has no default: the
    # ledger factory fails fast at startup when LEDGER_PROVIDER=hledger and it
    # is unset. HLEDGER_APPEND_FILE defaults to HLEDGER_FILE (single-file mode).
    HLEDGER_FILE: Path | None = None
    HLEDGER_APPEND_FILE: Path | None = None
    HLEDGER_BINARY: str = "hledger"
    HLEDGER_TIMEOUT_SECONDS: float = 10


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings."""
    return Settings()


def configure_logging(settings: Settings) -> None:
    """Configure structlog: JSON in production, coloured console output elsewhere."""
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if settings.ENVIRONMENT == "production"
        else structlog.dev.ConsoleRenderer()
    )
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=settings.LOG_LEVEL)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[settings.LOG_LEVEL]
        ),
        cache_logger_on_first_use=True,
    )
