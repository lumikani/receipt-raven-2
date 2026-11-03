"""Read use case for the account share default list."""

from src.application.classification.protocols.account_share_default_repository import (
    AccountShareDefaultRepositoryProtocol,
)
from src.domain.classification.entities.account_share_default import AccountShareDefault


class ListAccountShareDefaultsUseCase:
    """Serve every account share default, ordered by account."""

    def __init__(self, repository: AccountShareDefaultRepositoryProtocol) -> None:
        self.repository = repository

    async def list_account_share_defaults(self) -> list[AccountShareDefault]:
        return await self.repository.find_all()
