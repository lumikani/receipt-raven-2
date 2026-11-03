"""Port for storing Receipt aggregates."""

from typing import Protocol

from src.domain.common.value_objects import ReceiptId
from src.domain.receipts.entities.receipt import Receipt


class ReceiptRepositoryProtocol(Protocol):
    """Load and store Receipt aggregates, items included."""

    async def find_by_id(self, receipt_id: ReceiptId, /) -> Receipt | None:
        """Return the receipt, or ``None`` when there is no such receipt."""
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
