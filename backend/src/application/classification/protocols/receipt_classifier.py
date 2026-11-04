"""Port for stamping receipt items with the current classification rules."""

from typing import Protocol

from src.domain.receipts.entities.receipt import Receipt


class ReceiptClassifierProtocol(Protocol):
    """Applies the classification rules to a receipt's items."""

    async def stamp_receipt(self, receipt: Receipt, /) -> None:
        """Stamp every item that is not a manual classification override.

        Raises:
            ReceiptAlreadyApprovedError: If the receipt is approved; approved
                receipts are immutable and never re-classified.
        """
        ...
