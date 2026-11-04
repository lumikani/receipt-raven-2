"""Use case for approving a receipt: save the user's corrections, then book it."""

import structlog

from src.application.ledger.protocols.account_roles import AccountRolesProviderProtocol
from src.application.ledger.protocols.ledger_service import LedgerServiceProtocol
from src.application.receipts.commands.receipt_fields import ReceiptFields
from src.application.receipts.protocols.receipt_repository import ReceiptRepositoryProtocol
from src.domain.common.value_objects import ReceiptId
from src.domain.ledger.routing import build_routed_transaction
from src.domain.receipts.entities.receipt import Receipt
from src.domain.receipts.exceptions import ReceiptNotApprovableError, ReceiptNotFoundError

logger = structlog.get_logger(__name__)

# Currencies the ledger can take. The ledger's accounts are opened for EUR
# only, and how foreign-currency receipts should be booked is not decided
# yet, so other currencies are recorded but wait unapproved.
BOOKABLE_CURRENCIES = frozenset({"EUR"})


class ApproveReceiptUseCase:
    """Apply the user's edits and write the receipt to the ledger.

    The edits are saved before the ledger is called, so a rejected receipt
    keeps them and the user can fix the problem and approve again. Routing
    decides whether the receipt produces a ledger entry at all: a shared-card
    receipt whose rows are all shared is approved without being booked.
    """

    def __init__(
        self,
        receipt_repository: ReceiptRepositoryProtocol,
        ledger_service: LedgerServiceProtocol,
        account_roles: AccountRolesProviderProtocol,
    ) -> None:
        self.receipt_repository = receipt_repository
        self.ledger_service = ledger_service
        self.account_roles = account_roles

    async def approve_receipt(self, receipt_id: int, fields: ReceiptFields) -> Receipt:
        """Update and approve the receipt.

        Raises:
            ReceiptNotFoundError: If there is no such receipt.
            ReceiptAlreadyApprovedError: If it was approved before.
            ReceiptNotApprovableError: If the edited receipt breaks an approval rule,
                or is in a currency the ledger does not take yet.
            ExternalServiceError: If the ledger is down or rejects the receipt.

        The returned receipt is approved; its `booked` flag tells whether the
        approval wrote a ledger entry.
        """
        receipt = await self.receipt_repository.find_by_id(ReceiptId(receipt_id))
        if receipt is None:
            raise ReceiptNotFoundError(receipt_id)

        receipt.update_details(
            payee=fields.payee,
            receipt_date=fields.receipt_date,
            total_sum=fields.total_sum,
            description=fields.description,
            source_account=fields.source_account,
            currency=fields.currency,
        )
        receipt.replace_items(fields.lines)
        receipt = await self.receipt_repository.save(receipt)
        receipt.ensure_approvable()
        if receipt.currency not in BOOKABLE_CURRENCIES:
            raise ReceiptNotApprovableError(
                f"Receipts in {receipt.currency} cannot be booked to the ledger yet. "
                "Leave it unapproved for now."
            )

        transaction = build_routed_transaction(receipt, self.account_roles.load())
        if transaction is not None:
            await self.ledger_service.submit_receipt(transaction)

        receipt.approve(booked=transaction is not None)
        receipt = await self.receipt_repository.save(receipt)
        logger.info("receipt_approved", receipt_id=receipt_id, booked=receipt.booked)
        return receipt
