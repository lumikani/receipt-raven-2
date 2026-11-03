"""Request and response schemas for the receipts API."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

ReceiptStatusValue = Literal["unapproved", "approved"]
HeuristicLevelValue = Literal["WARN", "SEVERE", "ERROR"]


class OcrIssue(BaseModel):
    """A doubt the analysis has about a value it read."""

    level: HeuristicLevelValue
    message: str


class OcrNotes(BaseModel):
    """Issues found in an analysed receipt. Null fields passed their check."""

    suspicious_date: OcrIssue | None


class ReceiptItem(BaseModel):
    """One purchased product with its classification snapshot."""

    id: int
    name: str
    expense_account: str
    price: float
    flatmate_share: float = Field(
        0, description="Percentage of the price attributable to the flatmate"
    )
    matched_rule_id: int | None = Field(
        None, description="The classification rule that matched, if any"
    )
    classification_overridden: bool = Field(
        False, description="True when the account or share was edited manually"
    )


class ReceiptDocument(BaseModel):
    """The photo or PDF the receipt was read from."""

    url: str
    mime_type: str


class ReceiptSummary(BaseModel):
    """A receipt as the list shows it."""

    id: int
    payee: str
    description: str | None
    date: dt.date
    total_sum: float
    currency: str = Field(description="ISO 4217 code of every amount on the receipt")
    status: ReceiptStatusValue
    booked: bool = Field(False, description="True when approval wrote a ledger entry")
    source_account: str | None
    item_count: int
    has_ocr_issues: bool
    created_at: dt.datetime


class Receipt(BaseModel):
    """A receipt with its items."""

    id: int
    payee: str
    description: str | None
    date: dt.date
    total_sum: float
    currency: str = Field(description="ISO 4217 code of every amount on the receipt")
    status: ReceiptStatusValue
    booked: bool = Field(False, description="True when approval wrote a ledger entry")
    source_account: str | None
    card_last_digits: str | None = Field(
        None, description="Card digits read from the receipt, if any"
    )
    parsed_by: str
    items: list[ReceiptItem]
    ocr_notes: OcrNotes | None = Field(
        description="Analysis notes; null for receipts entered by hand"
    )
    document: ReceiptDocument | None
    job_id: int | None
    created_at: dt.datetime


class ReceiptLineRequest(BaseModel):
    """An item to keep (with `id`) or add (without)."""

    id: int | None = None
    name: str = Field(..., min_length=1, max_length=500)
    expense_account: str = Field("", max_length=500)
    price: float
    flatmate_share: float = Field(0, ge=0, le=100)


class ReceiptRequest(BaseModel):
    """Body of the create and approve requests."""

    payee: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    source_account: str | None = None
    date: dt.date
    total_sum: float
    currency: str = Field("EUR", pattern=r"^[A-Za-z]{3}$", description="ISO 4217 code")
    items: list[ReceiptLineRequest] = Field(..., min_length=1)


class ReclassifyAllResponse(BaseModel):
    """Result of the bulk re-classify action."""

    receipt_ids: list[int] = Field(description="The re-classified receipts, oldest first")


__all__ = [
    "OcrIssue",
    "OcrNotes",
    "Receipt",
    "ReceiptDocument",
    "ReceiptItem",
    "ReceiptLineRequest",
    "ReceiptRequest",
    "ReceiptStatusValue",
    "ReceiptSummary",
    "ReclassifyAllResponse",
]
