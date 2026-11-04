"""Read use case for the balancing export (CSV of eligible approved receipts)."""

from collections.abc import Collection
from datetime import date

from src.application.ledger.protocols.account_roles import AccountRolesProviderProtocol
from src.application.receipts.commands.approve_receipt_use_case import BOOKABLE_CURRENCIES
from src.application.receipts.protocols.receipt_repository import ReceiptRepositoryProtocol
from src.domain.ledger.export import BalancingExportRow, build_export_rows


class ExportReceiptsUseCase:
    """Build the balancing export rows for the selected receipts.

    Eligibility — approved, personal-card source account, bookable currency,
    at least one item with a flatmate share — is always applied by the domain
    function and cannot be overridden by the selection.
    """

    def __init__(
        self,
        receipt_repository: ReceiptRepositoryProtocol,
        account_roles: AccountRolesProviderProtocol,
    ) -> None:
        self.receipt_repository = receipt_repository
        self.account_roles = account_roles

    async def export_receipts(
        self,
        *,
        ids: Collection[int] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[BalancingExportRow]:
        """The export rows of the selected receipts, date-ascending then id."""
        receipts = await self.receipt_repository.find_all(
            ids=ids, from_date=from_date, to_date=to_date
        )
        return build_export_rows(receipts, self.account_roles.load(), BOOKABLE_CURRENCIES)
