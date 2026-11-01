"""Read model for the receipt list.

These are view DTOs, not domain entities: they exist to be rendered and must
never be fed back into a command (the `queries-are-dead-ends` import contract
enforces that). See `.agents/docs/adr/0001-read-models-and-query-services.md`.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from src.application.common.pagination import Page, PageRequest
from src.domain.receipts.entities.receipt import ReceiptStatus
from src.domain.receipts.ocr_notes import OcrNotes


@dataclass(frozen=True)
class ReceiptListItemView:
    """One row of the receipt list."""

    id: int
    payee: str
    description: str | None
    receipt_date: date
    total_sum: float
    currency: str
    status: ReceiptStatus
    source_account: str | None
    item_count: int
    has_ocr_issues: bool
    created_at: datetime


class ReceiptListQueryProtocol(Protocol):
    """Port for reading the receipt list."""

    async def list_receipts(
        self, page: PageRequest, status: ReceiptStatus | None
    ) -> Page[ReceiptListItemView]:
        """Return receipts, newest first, optionally of one status only."""
        ...


def has_issues(notes: OcrNotes | None) -> bool:
    """Whether the analysis left anything for the user to check."""
    return notes is not None and not notes.is_empty
