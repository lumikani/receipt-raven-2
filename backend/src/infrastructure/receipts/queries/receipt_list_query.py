"""Query adapter for the receipt list: columns and an item count, no aggregates."""

from collections.abc import Container

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.common.pagination import Page, PageRequest
from src.application.ledger.protocols.account_roles import AccountRolesProviderProtocol
from src.application.receipts.queries.receipt_list import ReceiptListItemView, has_issues
from src.domain.common.value_objects import SHARE_MIN
from src.domain.ledger.export import export_eligibility
from src.domain.receipts.entities.receipt import ReceiptStatus
from src.infrastructure.common.pagination import count_rows, page_of
from src.infrastructure.receipts.mappers.receipt_mapper import ocr_notes_from_json
from src.infrastructure.receipts.orm.receipt_model import ReceiptItemModel, ReceiptModel


class ReceiptListQuery:
    """Serves the receipt list read model."""

    def __init__(
        self,
        db: AsyncSession,
        account_roles: AccountRolesProviderProtocol,
        bookable_currencies: Container[str],
    ) -> None:
        self.db = db
        self.account_roles = account_roles
        self.bookable_currencies = bookable_currencies

    async def list_receipts(
        self, page: PageRequest, status: ReceiptStatus | None
    ) -> Page[ReceiptListItemView]:
        item_count = (
            select(func.count(ReceiptItemModel.id))
            .where(ReceiptItemModel.receipt_id == ReceiptModel.id)
            .scalar_subquery()
            .label("item_count")
        )
        has_shared_item = (
            select(func.count(ReceiptItemModel.id))
            .where(
                ReceiptItemModel.receipt_id == ReceiptModel.id,
                ReceiptItemModel.flatmate_share > SHARE_MIN,
            )
            .scalar_subquery()
            .label("has_shared_item")
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
            has_shared_item,
            ReceiptModel.ocr_notes,
            ReceiptModel.created_at,
        ).order_by(ReceiptModel.created_at.desc(), ReceiptModel.id.desc())
        if status is not None:
            stmt = stmt.where(ReceiptModel.status == status.value)

        roles = self.account_roles.load()
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
                    export_eligible=export_eligibility(
                        is_approved=row.status == ReceiptStatus.APPROVED.value,
                        source_account=row.source_account,
                        currency=row.currency,
                        has_shared_item=row.has_shared_item > 0,
                        account_roles=roles,
                        bookable_currencies=self.bookable_currencies,
                    ),
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
