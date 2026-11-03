"""Repository for Receipt aggregates."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.receipts.entities.receipt import Receipt, ReceiptStatus
from src.infrastructure.common.repositories import BaseRepository
from src.infrastructure.receipts.mappers.receipt_mapper import ReceiptMapper
from src.infrastructure.receipts.orm.receipt_model import ReceiptModel


class ReceiptRepository(BaseRepository[Receipt, ReceiptModel]):
    """Stores receipts with their items (loaded eagerly, deleted with the receipt)."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, ReceiptModel, ReceiptMapper())

    async def find_all_unapproved(self) -> list[Receipt]:
        """Every unapproved receipt, oldest first."""
        stmt = (
            select(ReceiptModel)
            .where(ReceiptModel.status == ReceiptStatus.UNAPPROVED.value)
            .order_by(ReceiptModel.id)
        )
        result = await self.db.execute(stmt)
        return [self._mapper.to_domain(row) for row in result.scalars().all()]
