"""Port to the AI model that reads receipts."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol


class ReceiptAnalysisError(Exception):
    """Raised when the model cannot be reached or its answer cannot be used."""


@dataclass(frozen=True)
class AnalysedProduct:
    """A line item as the model read it."""

    name: str
    expense_account: str
    price: float


@dataclass(frozen=True)
class ReceiptAnalysis:
    """What the model read from a receipt. `receipt_date` is None when unreadable.

    Prices and total are in `currency`, an ISO 4217 code.
    """

    payee: str
    description: str | None
    receipt_date: date | None
    products: tuple[AnalysedProduct, ...]
    total: float
    model: str
    currency: str = "EUR"
    # Card last digits read from the receipt (e.g. from a Finnish `Kortti:`
    # line). Only the local OCR parser sets it; cloud providers leave it None.
    card_last_digits: str | None = None


class ReceiptAnalyzerProtocol(Protocol):
    """Reads a receipt image or PDF."""

    async def analyze(
        self, document: bytes, mime_type: str, expense_accounts: list[str]
    ) -> ReceiptAnalysis:
        """Read the receipt, choosing each product's account from `expense_accounts`.

        Raises:
            ReceiptAnalysisError: If the model fails or answers with unusable data.
        """
        ...
