"""Read use case for the rule list."""

from src.application.classification.protocols.classification_rule_repository import (
    ClassificationRuleRepositoryProtocol,
)
from src.domain.classification.entities.classification_rule import ClassificationRule


class ListRulesUseCase:
    """Serve every rule, oldest first, from the repository port."""

    def __init__(self, rule_repository: ClassificationRuleRepositoryProtocol) -> None:
        self.rule_repository = rule_repository

    async def list_rules(self) -> list[ClassificationRule]:
        return await self.rule_repository.find_all()
