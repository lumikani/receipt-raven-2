"""Read use case for one classification rule."""

from src.application.classification.protocols.classification_rule_repository import (
    ClassificationRuleRepositoryProtocol,
)
from src.domain.classification.entities.classification_rule import ClassificationRule
from src.domain.classification.exceptions import ClassificationRuleNotFoundError
from src.domain.common.value_objects import ClassificationRuleId


class GetRuleUseCase:
    """Fetch a single rule by id."""

    def __init__(self, rule_repository: ClassificationRuleRepositoryProtocol) -> None:
        self.rule_repository = rule_repository

    async def get_rule(self, rule_id: int) -> ClassificationRule:
        rule = await self.rule_repository.find_by_id(ClassificationRuleId(rule_id))
        if rule is None:
            raise ClassificationRuleNotFoundError(rule_id)
        return rule
