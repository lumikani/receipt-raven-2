"""Repository for AccountShareDefault aggregates."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.classification.entities.account_share_default import AccountShareDefault
from src.infrastructure.classification.mappers.classification_mapper import (
    AccountShareDefaultMapper,
)
from src.infrastructure.classification.orm.classification_model import AccountShareDefaultModel
from src.infrastructure.common.repositories import BaseRepository


class AccountShareDefaultRepository(BaseRepository[AccountShareDefault, AccountShareDefaultModel]):
    """Stores per-account share defaults; one row per expense account."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, AccountShareDefaultModel, AccountShareDefaultMapper())

    async def find_all(self) -> list[AccountShareDefault]:
        stmt = select(AccountShareDefaultModel).order_by(AccountShareDefaultModel.expense_account)
        result = await self.db.execute(stmt)
        return [self._mapper.to_domain(row) for row in result.scalars().all()]

    async def find_by_account(self, expense_account: str) -> AccountShareDefault | None:
        stmt = select(AccountShareDefaultModel).where(
            AccountShareDefaultModel.expense_account == expense_account
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        return self._mapper.to_domain(row) if row is not None else None
