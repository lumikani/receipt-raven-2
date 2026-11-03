"""Use case for typing in a receipt by hand."""

import structlog

from src.application.classification.protocols.receipt_classifier import (
    ReceiptClassifierProtocol,
)
from src.application.receipts.commands.receipt_fields import ReceiptFields
from src.application.receipts.protocols.receipt_repository import ReceiptRepositoryProtocol
from src.domain.receipts.entities.receipt import Receipt

logger = structlog.get_logger(__name__)


class CreateReceiptUseCase:
    """Store a receipt the user entered, rule-pre-filled like an analysed one.

    It starts unapproved, like an analysed one.
    """

    def __init__(
        self,
        receipt_repository: ReceiptRepositoryProtocol,
        receipt_classifier: ReceiptClassifierProtocol,
    ) -> None:
        self.receipt_repository = receipt_repository
        self.receipt_classifier = receipt_classifier

    async def create_receipt(self, fields: ReceiptFields) -> Receipt:
        receipt = Receipt.create_manual(
            payee=fields.payee,
            receipt_date=fields.receipt_date,
            total_sum=fields.total_sum,
            lines=fields.lines,
            description=fields.description,
            source_account=fields.source_account,
            currency=fields.currency,
        )
        await self.receipt_classifier.stamp_receipt(receipt)
        receipt = await self.receipt_repository.save(receipt)
        logger.info("receipt_created", receipt_id=receipt.id.value)
        return receipt
