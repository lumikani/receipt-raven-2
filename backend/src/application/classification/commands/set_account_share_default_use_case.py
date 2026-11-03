"""Use case for setting an expense account's default flatmate share (upsert)."""

import structlog

from src.application.classification.commands.rule_fields import ensure_ledger_expense_account
from src.application.classification.protocols.account_share_default_repository import (
    AccountShareDefaultRepositoryProtocol,
)
from src.application.ledger.protocols.ledger_service import LedgerServiceProtocol
from src.domain.classification.entities.account_share_default import AccountShareDefault

logger = structlog.get_logger(__name__)


class SetAccountShareDefaultUseCase:
    """Create or update one account's share default.

    The account must be one of the ledger's expense accounts, like a rule's.
    """

    def __init__(
        self,
        repository: AccountShareDefaultRepositoryProtocol,
        ledger_service: LedgerServiceProtocol,
    ) -> None:
        self.repository = repository
        self.ledger_service = ledger_service

    async def set_account_share_default(
        self, expense_account: str, share: float
    ) -> AccountShareDefault:
        await ensure_ledger_expense_account(self.ledger_service, expense_account)
        existing = await self.repository.find_by_account(expense_account)
        if existing is None:
            default = AccountShareDefault.create(expense_account=expense_account, share=share)
        else:
            existing.update(share=share)
            default = existing
        saved = await self.repository.save(default)
        logger.info("account_share_default_set", expense_account=expense_account, share=share)
        return saved
