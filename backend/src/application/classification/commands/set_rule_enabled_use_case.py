"""Use case for enabling or disabling a classification rule."""

import structlog

from src.application.classification.protocols.classification_rule_repository import (
    ClassificationRuleRepositoryProtocol,
)
from src.domain.classification.entities.classification_rule import ClassificationRule
from src.domain.classification.exceptions import ClassificationRuleNotFoundError
from src.domain.common.value_objects import ClassificationRuleId

logger = structlog.get_logger(__name__)


class SetRuleEnabledUseCase:
    """Toggle a rule without touching its other fields. Disabled rules never match."""

    def __init__(self, rule_repository: ClassificationRuleRepositoryProtocol) -> None:
        self.rule_repository = rule_repository

    async def set_rule_enabled(self, rule_id: int, enabled: bool) -> ClassificationRule:
        rule = await self.rule_repository.find_by_id(ClassificationRuleId(rule_id))
        if rule is None:
            raise ClassificationRuleNotFoundError(rule_id)
        rule.set_enabled(enabled)
        saved = await self.rule_repository.save(rule)
        logger.info("classification_rule_enabled_changed", rule_id=saved.id.value, enabled=enabled)
        return saved
