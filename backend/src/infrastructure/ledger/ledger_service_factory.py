"""Choose the ledger service the settings ask for."""

from src.application.ledger.protocols.ledger_service import LedgerServiceProtocol
from src.config import Settings
from src.infrastructure.ledger.beancount_ledger_service import BeancountLedgerService
from src.infrastructure.ledger.hledger_ledger_service import HledgerLedgerService


def build_ledger_service(settings: Settings) -> LedgerServiceProtocol:
    """`LEDGER_PROVIDER`: beancount (default, the HTTP service) or hledger (the CLI)."""
    match settings.LEDGER_PROVIDER:
        case "beancount":
            return BeancountLedgerService(
                base_url=settings.BEANCOUNT_SERVICE_URL,
                timeout_seconds=settings.BEANCOUNT_TIMEOUT_SECONDS,
            )
        case "hledger":
            if settings.HLEDGER_FILE is None:
                raise ValueError(
                    "HLEDGER_FILE is required when LEDGER_PROVIDER=hledger "
                    "(the app never guesses which journal to read and write)"
                )
            return HledgerLedgerService(
                read_file=settings.HLEDGER_FILE,
                append_file=settings.HLEDGER_APPEND_FILE or settings.HLEDGER_FILE,
                binary=settings.HLEDGER_BINARY,
                timeout_seconds=settings.HLEDGER_TIMEOUT_SECONDS,
            )
