"""Unit tests for the Receipt aggregate's item replacement and balance rule."""

from datetime import date

import pytest

from src.domain.common.value_objects import ReceiptItemId
from src.domain.receipts.entities.receipt import Receipt, ReceiptLine, ReceiptStatus
from src.domain.receipts.exceptions import ReceiptNotApprovableError


def receipt(total: float, *prices: float) -> Receipt:
    return Receipt.create_manual(
        payee="Prisma",
        receipt_date=date(2026, 10, 9),
        total_sum=total,
        lines=[ReceiptLine(f"item {i}", "Expenses:Food", p) for i, p in enumerate(prices)],
        source_account="Assets:Checking",
    )


@pytest.mark.parametrize(
    ("total", "prices", "balanced"),
    [
        (0.3, (0.1, 0.2), True),  # floating-point sum 0.30000000000000004
        (10.0, (9.99,), False),
        (10.0, (10.004,), True),
    ],
)
def test_balance_is_checked_to_the_cent(
    total: float, prices: tuple[float, ...], balanced: bool
) -> None:
    assert receipt(total, *prices).is_balanced is balanced


def test_unbalanced_receipt_cannot_be_approved() -> None:
    with pytest.raises(ReceiptNotApprovableError):
        receipt(10.0, 9.0).approve(booked=True)


def test_approve_records_whether_a_ledger_entry_was_written() -> None:
    not_booked = receipt(10.0, 10.0)
    not_booked.approve(booked=False)
    booked = receipt(10.0, 10.0)
    booked.approve(booked=True)

    assert (not_booked.status, not_booked.booked) == (ReceiptStatus.APPROVED, False)
    assert (booked.status, booked.booked) == (ReceiptStatus.APPROVED, True)


def test_replace_items_ignores_ids_the_receipt_does_not_have() -> None:
    subject = receipt(3.0, 1.0, 2.0)
    subject.items[0].id = ReceiptItemId(7)

    subject.replace_items(
        [
            ReceiptLine("kept", "Expenses:Food", 1.0, item_id=ReceiptItemId(7)),
            ReceiptLine("stranger", "Expenses:Food", 5.0, item_id=ReceiptItemId(99)),
        ]
    )

    assert [(item.id.value, item.name) for item in subject.items] == [(7, "kept")]
