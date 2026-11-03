"""Query adapter for the receipt list: columns and an item count, no aggregates."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.common.pagination import Page, PageRequest
from src.application.receipts.queries.receipt_list import ReceiptListItemView, has_issues
from src.domain.receipts.entities.receipt import ReceiptStatus
from src.infrastructure.common.pagination import count_rows, page_of
from src.infrastructure.receipts.mappers.receipt_mapper import ocr_notes_from_json
from src.infrastructure.receipts.orm.receipt_model import ReceiptItemModel, ReceiptModel


class ReceiptListQuery:
    """Serves the receipt list read model."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_receipts(
        self, page: PageRequest, status: ReceiptStatus | None
    ) -> Page[ReceiptListItemView]:
        item_count = (
            select(func.count(ReceiptItemModel.id))
            .where(ReceiptItemModel.receipt_id == ReceiptModel.id)
            .scalar_subquery()
            .label("item_count")
        )
        stmt = select(
            ReceiptModel.id,
            ReceiptModel.payee,
            ReceiptModel.description,
            ReceiptModel.receipt_date,
            ReceiptModel.total_sum,
            ReceiptModel.currency,
            ReceiptModel.status,
            ReceiptModel.booked,
            ReceiptModel.source_account,
            item_count,
            ReceiptModel.ocr_notes,
            ReceiptModel.created_at,
        ).order_by(ReceiptModel.created_at.desc(), ReceiptModel.id.desc())
        if status is not None:
            stmt = stmt.where(ReceiptModel.status == status.value)

        total = await count_rows(self.db, stmt)
        rows = await self.db.execute(page_of(stmt, page))
        return Page(
            items=tuple(
                ReceiptListItemView(
                    id=row.id,
                    payee=row.payee,
                    description=row.description,
                    receipt_date=row.receipt_date,
                    total_sum=row.total_sum,
                    currency=row.currency,
                    status=ReceiptStatus(row.status),
                    booked=row.booked,
                    source_account=row.source_account,
                    item_count=row.item_count,
                    has_ocr_issues=has_issues(ocr_notes_from_json(row.ocr_notes)),
                    created_at=row.created_at,
                )
                for row in rows
            ),
            total=total,
            offset=page.offset,
            limit=page.limit,
        )
