"""The editable fields of a classification rule, shared by create and update."""

from dataclasses import dataclass

from src.application.ledger.protocols.ledger_service import LedgerServiceProtocol
from src.domain.common.exceptions import ValidationError
from src.domain.ledger.account import AccountType


@dataclass(frozen=True)
class RuleFields:
    """What a rule request carries."""

    pattern: str
    max_typos: int
    expense_account: str
    flatmate_share_override: float | None
    enabled: bool


async def ensure_ledger_expense_account(
    ledger_service: LedgerServiceProtocol, expense_account: str
) -> None:
    """Rules pick accounts from the ledger's expense account list only.

    Raises:
        ValidationError: If the account is not an open expense account.
    """
    accounts = await ledger_service.list_accounts(AccountType.EXPENSES)
    names = {account.name for account in accounts}
    if expense_account not in names:
        raise ValidationError(
            f"'{expense_account}' is not an expense account in the ledger",
            field="expense_account",
            value=expense_account,
        )
