"""Response schemas for the ledger API."""

from typing import Literal

from pydantic import BaseModel

AccountTypeValue = Literal["Assets", "Liabilities", "Equity", "Income", "Expenses"]


class LedgerAccount(BaseModel):
    """An open ledger account."""

    name: str
    type: AccountTypeValue


class AccountRolesResponse(BaseModel):
    """The configured source-account roles, for the review screen's routing preview.

    Null fields mean "not configured"; an empty `personal_cards` with a null
    `shared_card` routes every source account as a personal card.
    """

    personal_cards: list[str]
    shared_card: str | None
    flatmate_expense_adjustment: str | None
    purchase_for_flatmate: str | None
    # The account items no rule matches land on.
    unallocated_account: str


__all__ = ["AccountRolesResponse", "AccountTypeValue", "LedgerAccount"]
