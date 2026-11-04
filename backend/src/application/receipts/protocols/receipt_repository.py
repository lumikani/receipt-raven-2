"""Port for storing Receipt aggregates."""

from collections.abc import Collection
from datetime import date
from typing import Protocol

from src.domain.common.value_objects import ReceiptId
from src.domain.receipts.entities.receipt import Receipt


class ReceiptRepositoryProtocol(Protocol):
    """Load and store Receipt aggregates, items included."""

    async def find_by_id(self, receipt_id: ReceiptId, /) -> Receipt | None:
        """Return the receipt, or ``None`` when there is no such receipt."""
        ...

    async def find_all(
        self,
        /,
        *,
        ids: Collection[int] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[Receipt]:
        """Receipts matching the selection, date-ascending then id-ascending.

        No filters means every receipt; reads like the balancing export apply
        their own eligibility on top.
        """
        ...

    async def find_all_unapproved(self) -> list[Receipt]:
        """Every unapproved receipt, oldest first."""
        ...

    async def save(self, receipt: Receipt, /) -> Receipt:
        """Insert a new receipt (id 0) or update an existing one."""
        ...

    async def delete(self, receipt_id: ReceiptId, /) -> bool:
        """Delete a receipt. Returns False if there was no such receipt."""
        ...
