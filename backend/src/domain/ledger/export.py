"""The balancing export: one row per eligible approved personal-card receipt.

The export feeds the flatmate's balancing spreadsheet, so its numbers follow
the spreadsheet's semantics exactly: all arithmetic happens in
`decimal.Decimal` (floats enter only as `Decimal(str(price))`, their shortest
exact form) and each column is rounded once, half-up, to two decimals.

Eligibility is always the same and never overridable: the receipt is approved,
its source account plays the personal-card role, its currency is bookable, and
at least one item has a flatmate share above 0. Shared-card receipts are never
eligible.

The receipt is typed structurally (`ExportableReceipt`) because domain modules
must not import each other; the receipts aggregate satisfies it.
"""

from collections.abc import Container, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from src.domain.common.value_objects import SHARE_MAX, SHARE_MIN
from src.domain.ledger.account_roles import AccountRole, AccountRoles
from src.domain.ledger.routing import RoutableReceipt, RoutableReceiptItem

CENT = Decimal("0.01")
_HUNDRED = Decimal(100)
_TWO = Decimal(2)


@dataclass(frozen=True)
class BalancingExportRow:
    """One export row: the columns `shared_cost,description,purchase_for_flatmate`."""

    shared_cost: Decimal
    description: str
    purchase_for_flatmate: Decimal


class ExportableReceipt(RoutableReceipt, Protocol):
    """A routable receipt that also knows whether it is approved."""

    @property
    def is_approved(self) -> bool: ...


def is_export_eligible(
    receipt: ExportableReceipt,
    account_roles: AccountRoles,
    bookable_currencies: Container[str],
) -> bool:
    """Whether the receipt gets an export row (see the module docstring)."""
    return (
        receipt.is_approved
        and account_roles.role_of(receipt.source_account) is AccountRole.PERSONAL_CARD
        and receipt.currency in bookable_currencies
        and any(item.flatmate_share > SHARE_MIN for item in receipt.items)
    )


def export_row(
    receipt: ExportableReceipt,
    account_roles: AccountRoles,
    bookable_currencies: Container[str],
) -> BalancingExportRow | None:
    """The receipt's one export row, or None when it is not eligible.

    `shared_cost` is what the flatmate owes for the partially shared items:
    the sum of 2 x (share/100) x price over items with 0 < share < 100.
    `purchase_for_flatmate` is the sum of the prices of the items bought
    entirely for the flatmate (share 100).
    """
    if not is_export_eligible(receipt, account_roles, bookable_currencies):
        return None
    shared_cost = sum(
        (
            _TWO * (Decimal(str(item.flatmate_share)) / _HUNDRED) * _price(item)
            for item in receipt.items
            if SHARE_MIN < item.flatmate_share < SHARE_MAX
        ),
        Decimal(0),
    )
    purchase_for_flatmate = sum(
        (_price(item) for item in receipt.items if item.flatmate_share == SHARE_MAX),
        Decimal(0),
    )
    return BalancingExportRow(
        shared_cost=shared_cost.quantize(CENT, rounding=ROUND_HALF_UP),
        description=_description(receipt),
        purchase_for_flatmate=purchase_for_flatmate.quantize(CENT, rounding=ROUND_HALF_UP),
    )


def build_export_rows(
    receipts: Sequence[ExportableReceipt],
    account_roles: AccountRoles,
    bookable_currencies: Container[str],
) -> list[BalancingExportRow]:
    """The export rows of the eligible receipts, in the order given."""
    rows = []
    for receipt in receipts:
        row = export_row(receipt, account_roles, bookable_currencies)
        if row is not None:
            rows.append(row)
    return rows


def _price(item: RoutableReceiptItem) -> Decimal:
    """The item price as an exact decimal (the float's shortest repr)."""
    return Decimal(str(item.price))


def _description(receipt: ExportableReceipt) -> str:
    """`MM-DD {payee as stored} {description, or the item names joined with ", "}`."""
    detail = receipt.description or ", ".join(item.name for item in receipt.items)
    return f"{receipt.receipt_date:%m-%d} {receipt.payee} {detail}"
