"""Use case for re-running the classification rules on every unapproved receipt."""

import structlog

from src.application.classification.protocols.receipt_classifier import (
    ReceiptClassifierProtocol,
)
from src.application.receipts.protocols.receipt_repository import ReceiptRepositoryProtocol
from src.domain.receipts.entities.receipt import Receipt

logger = structlog.get_logger(__name__)


class ReclassifyAllUnapprovedUseCase:
    """Bulk re-classify of the receipt list's unapproved receipts."""

    def __init__(
        self,
        receipt_repository: ReceiptRepositoryProtocol,
        receipt_classifier: ReceiptClassifierProtocol,
    ) -> None:
        self.receipt_repository = receipt_repository
        self.receipt_classifier = receipt_classifier

    async def reclassify_all_unapproved(self) -> list[Receipt]:
        """Re-classify every unapproved receipt; return them, oldest first."""
        receipts = await self.receipt_repository.find_all_unapproved()
        for receipt in receipts:
            await self.receipt_classifier.stamp_receipt(receipt)
            await self.receipt_repository.save(receipt)
        logger.info("receipts_reclassified", count=len(receipts))
        return receipts
