"""The classification verdict for one receipt item, shared across domain modules."""

from dataclasses import dataclass

from src.domain.common.value_object import ValueObject
from src.domain.common.value_objects.ids import ClassificationRuleId


@dataclass(frozen=True)
class ClassificationStamp(ValueObject):
    """What a classification rule decided for one item.

    `matched_rule_id` is the rule that matched (null when none did or the item
    was manually overridden).
    """

    expense_account: str
    flatmate_share: float
    matched_rule_id: ClassificationRuleId | None
