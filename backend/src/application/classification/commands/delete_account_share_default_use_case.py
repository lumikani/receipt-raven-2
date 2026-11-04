"""Use case for deleting an expense account's share default."""

import structlog

from src.application.classification.protocols.account_share_default_repository import (
    AccountShareDefaultRepositoryProtocol,
)
from src.domain.classification.exceptions import AccountShareDefaultNotFoundError

logger = structlog.get_logger(__name__)


class DeleteAccountShareDefaultUseCase:
    """Delete one account's default; items then fall back to 0% + flag."""

    def __init__(self, repository: AccountShareDefaultRepositoryProtocol) -> None:
        self.repository = repository

    async def delete_account_share_default(self, expense_account: str) -> None:
        existing = await self.repository.find_by_account(expense_account)
        if existing is None:
            raise AccountShareDefaultNotFoundError(expense_account)
        await self.repository.delete(existing.id)
        logger.info("account_share_default_deleted", expense_account=expense_account)
