"""Ledger routing: the one entry a receipt becomes, built as a pure function.

Routing depends on the source account's configured role and each item's
flatmate share only — never on other classification inputs. Signs follow the
beancount convention: expenses positive, liabilities negative.

- Personal card: one transaction, every row a positive posting merged per
  account; share-100 rows are remapped to the configured
  purchase-for-flatmate account. `total` is the receipt total; the renderer
  adds the -sum balancing leg on the card liability.
- Shared card: rows with 0 < share < 100 are routed nowhere. An entry exists
  iff at least one row has share 0 or 100: share-0 rows become merged positive
  expense postings plus a credit (negative) on the shared-account liability;
  share-100 rows become one merged negative posting on the flatmate expense
  adjustment account plus a debit (positive) on the shared liability. The legs
  sum to zero, so the renderer adds no balancing leg. If every row is shared,
  there is no entry at all (`None`): the receipt is approved without being
  booked.

The receipt is typed structurally (`RoutableReceipt`) because domain modules
must not import each other; the receipts aggregate satisfies it.
"""

from collections.abc import Sequence
from datetime import date
from typing import Protocol

from src.domain.common.exceptions import ValidationError
from src.domain.common.value_objects import SHARE_MAX, SHARE_MIN, ReceiptId
from src.domain.ledger.account_roles import AccountRole, AccountRoles
from src.domain.ledger.receipt_transaction import (
    ReceiptPosting,
    ReceiptTransaction,
    merge_postings_by_account,
)


class RoutableReceiptItem(Protocol):
    """The item fields routing reads."""

    @property
    def name(self) -> str: ...

    @property
    def expense_account(self) -> str: ...

    @property
    def price(self) -> float: ...

    @property
    def flatmate_share(self) -> float: ...


class RoutableReceipt(Protocol):
    """The receipt fields routing reads."""

    @property
    def id(self) -> ReceiptId: ...

    @property
    def payee(self) -> str: ...

    @property
    def description(self) -> str | None: ...

    @property
    def receipt_date(self) -> date: ...

    @property
    def source_account(self) -> str | None: ...

    @property
    def total_sum(self) -> float: ...

    @property
    def currency(self) -> str: ...

    @property
    def items(self) -> Sequence[RoutableReceiptItem]: ...


def build_routed_transaction(
    receipt: RoutableReceipt, account_roles: AccountRoles
) -> ReceiptTransaction | None:
    """Build the receipt's one ledger entry, or None when nothing is booked.

    None means the shared card paid and every row is shared
    (0 < flatmate share < 100): approve without any ledger entry.
    """
    source_account = receipt.source_account or ""
    if account_roles.role_of(source_account) is AccountRole.SHARED_CARD:
        return _shared_card_transaction(receipt, account_roles, source_account)
    return _personal_card_transaction(receipt, account_roles, source_account)


def _merged_posting(
    items: Sequence[RoutableReceiptItem], expense_account: str, sign: float = 1.0
) -> ReceiptPosting:
    """One posting covering `items`, their prices summed, rounded to the cent."""
    return ReceiptPosting(
        name=", ".join(item.name for item in items),
        expense_account=expense_account,
        price=round(sign * sum(item.price for item in items), 2),
    )


def _transaction(
    receipt: RoutableReceipt, source_account: str, postings: Sequence[ReceiptPosting]
) -> ReceiptTransaction:
    """The receipt's one ledger entry with exactly these postings (unmerged)."""
    return ReceiptTransaction(
        receipt_id=receipt.id.value,
        payee=receipt.payee,
        description=receipt.description,
        receipt_date=receipt.receipt_date,
        source_account=source_account,
        total=receipt.total_sum,
        currency=receipt.currency,
        postings=tuple(postings),
    )


def _personal_card_transaction(
    receipt: RoutableReceipt, account_roles: AccountRoles, source_account: str
) -> ReceiptTransaction:
    """Every row a positive posting; share-100 rows remapped to purchase-for-flatmate."""
    purchase_for_flatmate = account_roles.purchase_for_flatmate
    items = [
        ReceiptPosting(
            name=item.name,
            expense_account=(
                purchase_for_flatmate
                if item.flatmate_share == SHARE_MAX and purchase_for_flatmate is not None
                else item.expense_account
            ),
            price=item.price,
        )
        for item in receipt.items
    ]
    return _transaction(receipt, source_account, merge_postings_by_account(items))


def _shared_card_transaction(
    receipt: RoutableReceipt, account_roles: AccountRoles, source_account: str
) -> ReceiptTransaction | None:
    """Book only share-0 and share-100 rows, as legs that sum to zero."""
    mine = [item for item in receipt.items if item.flatmate_share == SHARE_MIN]
    flatmates = [item for item in receipt.items if item.flatmate_share == SHARE_MAX]
    if not mine and not flatmates:
        return None
    adjustment = account_roles.flatmate_expense_adjustment
    if adjustment is None:
        # Unreachable by AccountRoles' validation: a configured shared card
        # always comes with the adjustment account.
        raise ValidationError(
            "Shared-card routing needs the flatmate expense adjustment account",
            field="flatmate_expense_adjustment",
        )

    postings: list[ReceiptPosting] = [
        # My rows: positive expense postings, merged per account.
        *merge_postings_by_account(
            [
                ReceiptPosting(
                    name=item.name, expense_account=item.expense_account, price=item.price
                )
                for item in mine
            ]
        )
    ]
    if flatmates:
        # Flatmate's rows: one merged negative posting on the adjustment account.
        postings.append(_merged_posting(flatmates, adjustment, sign=-1.0))
    # The shared-account liability legs stay separate (the renderer emits
    # postings unmerged): a credit for what I owe, a debit for what the
    # shared account owes me. Net: -(sum mine) + (sum flatmate's).
    if mine:
        postings.append(_merged_posting(mine, source_account, sign=-1.0))
    if flatmates:
        postings.append(_merged_posting(flatmates, source_account, sign=1.0))
    return _transaction(receipt, source_account, postings)
