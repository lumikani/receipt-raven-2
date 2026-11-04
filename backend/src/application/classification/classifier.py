"""Stamps receipt items from the current rules and account share defaults.

Used wherever a receipt's items get (re-)classified: right after the analysis
runs, when a receipt is entered by hand, and on the manual re-classify actions.
The stamp is a snapshot on the item; nothing re-classifies behind the user's
back.
"""

from src.application.classification.protocols.account_share_default_repository import (
    AccountShareDefaultRepositoryProtocol,
)
from src.application.classification.protocols.classification_rule_repository import (
    ClassificationRuleRepositoryProtocol,
)
from src.application.classification.protocols.receipt_classifier import (
    ReceiptClassifierProtocol,
)
from src.domain.classification.services.rule_engine import classify_item
from src.domain.common.value_objects import ClassificationStamp
from src.domain.receipts.entities.receipt import Receipt, ReceiptItem


class ReceiptClassifier(ReceiptClassifierProtocol):
    """Loads the rules and share defaults, then stamps each un-overridden item.

    A matching rule beats the account the analyzer or the user chose; with no
    match that account stays, and an empty one (the local parser) falls back to
    the unallocated account. Items whose account or share the user edited are
    manual overrides and are skipped.
    """

    def __init__(
        self,
        *,
        rule_repository: ClassificationRuleRepositoryProtocol,
        share_default_repository: AccountShareDefaultRepositoryProtocol,
        unallocated_account: str,
    ) -> None:
        self.rule_repository = rule_repository
        self.share_default_repository = share_default_repository
        self.unallocated_account = unallocated_account

    async def stamp_receipt(self, receipt: Receipt, /) -> None:
        rules = await self.rule_repository.find_all()
        defaults = {
            default.expense_account: default.share
            for default in await self.share_default_repository.find_all()
        }

        def classify(item: ReceiptItem) -> ClassificationStamp:
            result = classify_item(
                item.name,
                rules,
                defaults,
                self.unallocated_account,
                fallback_account=item.expense_account or None,
            )
            return ClassificationStamp(
                expense_account=result.expense_account,
                flatmate_share=result.flatmate_share,
                matched_rule_id=result.matched_rule_id,
            )

        receipt.apply_classification(classify)
