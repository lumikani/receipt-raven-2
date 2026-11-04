"""Hand-written fakes for the app's external services."""

from dataclasses import dataclass, field
from datetime import date

from src.application.analysis.protocols.receipt_analyzer import (
    AnalysedProduct,
    ReceiptAnalysis,
    ReceiptAnalysisError,
)
from src.domain.ledger.account import AccountType, LedgerAccount
from src.domain.ledger.account_roles import AccountRoles
from src.domain.ledger.exceptions import LedgerRejectedTransactionError, LedgerUnavailableError
from src.domain.ledger.receipt_transaction import ReceiptTransaction

DEFAULT_ACCOUNTS = [
    LedgerAccount("Assets:Checking", AccountType.ASSETS),
    LedgerAccount("Liabilities:CreditCard", AccountType.LIABILITIES),
    LedgerAccount("Expenses:Groceries", AccountType.EXPENSES),
    LedgerAccount("Expenses:Clothes", AccountType.EXPENSES),
    LedgerAccount("Income:Salary", AccountType.INCOME),
]


@dataclass
class FakeLedger:
    """An in-memory ledger that records what is submitted to it."""

    accounts: list[LedgerAccount] = field(default_factory=lambda: list(DEFAULT_ACCOUNTS))
    payees: list[str] = field(default_factory=lambda: ["Prisma", "K-Market", "Alko", "Prisma"])
    submitted: list[ReceiptTransaction] = field(default_factory=list)
    unavailable: bool = False
    reject_with: str | None = None

    def _check_available(self) -> None:
        if self.unavailable:
            raise LedgerUnavailableError("connection refused")

    async def list_accounts(self, account_type: AccountType | None = None) -> list[LedgerAccount]:
        self._check_available()
        return [a for a in self.accounts if account_type is None or a.type is account_type]

    async def list_payees(self) -> list[str]:
        self._check_available()
        return list(self.payees)

    async def submit_receipt(self, transaction: ReceiptTransaction) -> None:
        self._check_available()
        if self.reject_with is not None:
            raise LedgerRejectedTransactionError(self.reject_with)
        self.submitted.append(transaction)


@dataclass
class FakeAccountRoles:
    """Supplies fixed source-account roles to the use cases under test."""

    roles: AccountRoles = field(default_factory=AccountRoles)

    def load(self) -> AccountRoles:
        return self.roles


def analysis(
    *,
    payee: str = "K-Market",
    receipt_date: date | None = None,
    products: tuple[tuple[str, str, float], ...] = (
        ("Banaani", "Expenses:Groceries", 0.8),
        ("T-paita", "Expenses:Clothes", 14.99),
    ),
    total: float = 15.79,
    currency: str = "EUR",
    card_last_digits: str | None = None,
) -> ReceiptAnalysis:
    return ReceiptAnalysis(
        payee=payee,
        description="Ruokaa ja paita",
        receipt_date=receipt_date,
        products=tuple(AnalysedProduct(name, account, price) for name, account, price in products),
        total=total,
        model="fake-model",
        currency=currency,
        card_last_digits=card_last_digits,
    )


@dataclass
class FakeReceiptAnalyzer:
    """Answers with `result`, or fails with `error`. Records the accounts it was offered."""

    result: ReceiptAnalysis = field(default_factory=analysis)
    error: str | None = None
    offered_accounts: list[list[str]] = field(default_factory=list)

    async def analyze(
        self, document: bytes, mime_type: str, expense_accounts: list[str]
    ) -> ReceiptAnalysis:
        self.offered_accounts.append(expense_accounts)
        if self.error is not None:
            raise ReceiptAnalysisError(self.error)
        return self.result
