"""Use case for re-running the classification rules on one receipt."""

import structlog

from src.application.classification.protocols.receipt_classifier import (
    ReceiptClassifierProtocol,
)
from src.application.receipts.protocols.receipt_repository import ReceiptRepositoryProtocol
from src.domain.common.value_objects import ReceiptId
from src.domain.receipts.entities.receipt import Receipt
from src.domain.receipts.exceptions import ReceiptNotFoundError

logger = structlog.get_logger(__name__)


class ReclassifyReceiptUseCase:
    """Re-classify one unapproved receipt; manual overrides are skipped."""

    def __init__(
        self,
        receipt_repository: ReceiptRepositoryProtocol,
        receipt_classifier: ReceiptClassifierProtocol,
    ) -> None:
        self.receipt_repository = receipt_repository
        self.receipt_classifier = receipt_classifier

    async def reclassify_receipt(self, receipt_id: int) -> Receipt:
        """Stamp the receipt's items with the current rules and store it.

        Raises:
            ReceiptNotFoundError: If there is no such receipt.
            ReceiptAlreadyApprovedError: If it is approved; approved receipts
                are immutable and never re-classified.
        """
        receipt = await self.receipt_repository.find_by_id(ReceiptId(receipt_id))
        if receipt is None:
            raise ReceiptNotFoundError(receipt_id)
        await self.receipt_classifier.stamp_receipt(receipt)
        receipt = await self.receipt_repository.save(receipt)
        logger.info("receipt_reclassified", receipt_id=receipt_id)
        return receipt
