"""Receipt aggregate: one purchase, its line items and its way into the ledger.

A receipt starts unapproved, either read from an uploaded document by the
analysis or typed in by the user. The user corrects it and approves it, which
writes it to the ledger; from then on it is final.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum

from src.domain.common.aggregate_root import AggregateRoot
from src.domain.common.entity import Entity
from src.domain.common.exceptions import ValidationError
from src.domain.common.value_object import ValueObject
from src.domain.common.value_objects import (
    ClassificationRuleId,
    ReceiptId,
    ReceiptItemId,
    ReceiptJobId,
    check_share,
)
from src.domain.receipts.exceptions import (
    ReceiptAlreadyApprovedError,
    ReceiptNotApprovableError,
)
from src.domain.receipts.ocr_notes import OcrNotes

# Who produced a value: the analysis records its model name instead.
PARSED_BY_USER = "user"

# Item prices must add up to the total to the cent, as the ledger balances them.
BALANCE_TOLERANCE = 0.005

# Amounts are in this currency unless the receipt says otherwise.
DEFAULT_CURRENCY = "EUR"
_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")

# Flatmate share of an item's price is validated by common's check_share.


class ReceiptStatus(StrEnum):
    """Whether the receipt has been written to the ledger."""

    UNAPPROVED = "unapproved"
    APPROVED = "approved"


def _required_text(value: str, field_name: str, label: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValidationError(f"{label} cannot be empty", field=field_name)
    return stripped


def currency_code(value: str) -> str:
    """An ISO 4217 code such as EUR or JPY, upper-cased."""
    code = value.strip().upper()
    if not _CURRENCY_CODE.match(code):
        raise ValidationError(
            "Currency must be a three-letter code such as EUR or JPY", field="currency", value=value
        )
    return code


def _finite(value: float, field_name: str, label: str) -> float:
    if not math.isfinite(value):
        raise ValidationError(f"{label} must be a number", field=field_name, value=value)
    return value


@dataclass(frozen=True)
class ReceiptLine(ValueObject):
    """A line item as the user or the analysis submits it.

    `item_id` names an existing item to update; None adds a new one.
    """

    name: str
    expense_account: str
    price: float
    item_id: ReceiptItemId | None = None
    flatmate_share: float = 0.0


@dataclass(eq=False)
class ReceiptItem(Entity[ReceiptItemId]):
    """One purchased product, its expense account and its flatmate share.

    `matched_rule_id` is the classification rule that stamped the item (null
    when unmatched); `classification_overridden` marks a manual edit of the
    account or share, which re-classification skips.
    """

    id: ReceiptItemId
    name: str
    expense_account: str
    price: float
    parsed_by: str
    flatmate_share: float = 0.0
    matched_rule_id: ClassificationRuleId | None = None
    classification_overridden: bool = False

    def __post_init__(self) -> None:
        self.name = _required_text(self.name, "name", "Item name")
        self.expense_account = self.expense_account.strip()
        self.price = _finite(self.price, "price", "Item price")
        check_share(self.flatmate_share, "flatmate_share")

    @classmethod
    def from_line(cls, line: ReceiptLine, parsed_by: str) -> ReceiptItem:
        return cls(
            id=ReceiptItemId.generate(),
            name=line.name,
            expense_account=line.expense_account,
            price=line.price,
            parsed_by=parsed_by,
            flatmate_share=line.flatmate_share,
        )


@dataclass(eq=False)
class Receipt(AggregateRoot[ReceiptId]):
    """
    A purchase to be booked to the ledger.

    Business rules:
    - The payee cannot be empty; item names cannot be empty
    - An approved receipt is final: it cannot be edited or approved again
    - Approval needs a source account, at least one item, an expense account on
      every item, and item prices that add up to the total
    - All amounts are in the receipt's one currency, and the ledger books them in it
    """

    id: ReceiptId
    payee: str
    receipt_date: date
    total_sum: float
    items: list[ReceiptItem]
    parsed_by: str
    description: str | None = None
    source_account: str | None = None
    currency: str = DEFAULT_CURRENCY
    status: ReceiptStatus = ReceiptStatus.UNAPPROVED
    # True only after a successful ledger submit on approval.
    booked: bool = False
    # Card last digits the analysis read from the receipt, e.g. from a `Kortti:` line.
    card_last_digits: str | None = None
    job_id: ReceiptJobId | None = None
    document_filename: str | None = None
    document_mime_type: str | None = None
    ocr_notes: OcrNotes | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.payee = _required_text(self.payee, "payee", "Payee")
        self.total_sum = _finite(self.total_sum, "total_sum", "Total sum")
        self.description = self._optional_text(self.description)
        self.source_account = self._optional_text(self.source_account)
        self.currency = currency_code(self.currency)

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    # Creation

    @classmethod
    def create_manual(
        cls,
        *,
        payee: str,
        receipt_date: date,
        total_sum: float,
        lines: list[ReceiptLine],
        description: str | None = None,
        source_account: str | None = None,
        currency: str = DEFAULT_CURRENCY,
    ) -> Receipt:
        """A receipt the user typed in. It has no document and no analysis notes."""
        return cls(
            id=ReceiptId.generate(),
            payee=payee,
            receipt_date=receipt_date,
            total_sum=total_sum,
            items=[ReceiptItem.from_line(line, PARSED_BY_USER) for line in lines],
            parsed_by=PARSED_BY_USER,
            description=description,
            source_account=source_account,
            currency=currency,
        )

    @classmethod
    def create_from_analysis(
        cls,
        *,
        job_id: ReceiptJobId,
        document_filename: str,
        document_mime_type: str,
        payee: str,
        receipt_date: date,
        total_sum: float,
        lines: list[ReceiptLine],
        parsed_by: str,
        ocr_notes: OcrNotes,
        description: str | None = None,
        source_account: str | None = None,
        currency: str = DEFAULT_CURRENCY,
    ) -> Receipt:
        """A receipt the analysis read from an uploaded document."""
        return cls(
            id=ReceiptId.generate(),
            payee=payee,
            receipt_date=receipt_date,
            total_sum=total_sum,
            items=[ReceiptItem.from_line(line, parsed_by) for line in lines],
            parsed_by=parsed_by,
            description=description,
            source_account=source_account,
            currency=currency,
            job_id=job_id,
            document_filename=document_filename,
            document_mime_type=document_mime_type,
            ocr_notes=ocr_notes,
        )

    # Queries

    @property
    def is_approved(self) -> bool:
        return self.status is ReceiptStatus.APPROVED

    @property
    def items_sum(self) -> float:
        return sum(item.price for item in self.items)

    @property
    def is_balanced(self) -> bool:
        """Whether the item prices add up to the total, to the cent."""
        return abs(round(self.items_sum - self.total_sum, 2)) < BALANCE_TOLERANCE

    # Commands

    def update_details(
        self,
        *,
        payee: str,
        receipt_date: date,
        total_sum: float,
        description: str | None,
        source_account: str | None,
        currency: str,
    ) -> None:
        """Replace the receipt's header fields."""
        self._ensure_editable()
        self.currency = currency_code(currency)
        self.payee = _required_text(payee, "payee", "Payee")
        self.receipt_date = receipt_date
        self.total_sum = _finite(total_sum, "total_sum", "Total sum")
        self.description = self._optional_text(description)
        self.source_account = self._optional_text(source_account)

    def replace_items(self, lines: list[ReceiptLine]) -> None:
        """Make the item list match `lines`.

        A line with the id of an existing item updates that item; a line without
        an id adds an item; existing items no line mentions are removed. A line
        naming an id this receipt does not have is ignored.
        """
        self._ensure_editable()
        existing = {item.id: item for item in self.items}
        updated: list[ReceiptItem] = []
        for line in lines:
            if line.item_id is None:
                updated.append(ReceiptItem.from_line(line, PARSED_BY_USER))
                continue
            item = existing.get(line.item_id)
            if item is None:
                continue
            updated.append(
                ReceiptItem(
                    id=item.id,
                    name=line.name,
                    expense_account=line.expense_account,
                    price=line.price,
                    parsed_by=item.parsed_by,
                    flatmate_share=line.flatmate_share,
                    matched_rule_id=item.matched_rule_id,
                    classification_overridden=item.classification_overridden,
                )
            )
        self.items = updated

    def ensure_approvable(self) -> None:
        """Check every rule approval needs, before anything is sent to the ledger.

        Raises:
            ReceiptAlreadyApprovedError: If the receipt is already approved.
            ReceiptNotApprovableError: If a rule for approval is not met.
        """
        self._ensure_editable()
        if not self.source_account:
            raise ReceiptNotApprovableError("Choose the account the receipt was paid from")
        if not self.items:
            raise ReceiptNotApprovableError("A receipt needs at least one item")
        if any(not item.expense_account for item in self.items):
            raise ReceiptNotApprovableError("Every item needs an expense account")
        if not self.is_balanced:
            raise ReceiptNotApprovableError(
                f"Items add up to {self.items_sum:.2f} {self.currency}, "
                f"but the total is {self.total_sum:.2f} {self.currency}"
            )

    def approve(self) -> None:
        """Mark the receipt as written to the ledger."""
        self.ensure_approvable()
        self.status = ReceiptStatus.APPROVED

    def _ensure_editable(self) -> None:
        if self.is_approved:
            raise ReceiptAlreadyApprovedError(self.id.value)
