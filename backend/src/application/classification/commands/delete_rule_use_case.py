"""Use case for deleting a classification rule."""

import structlog

from src.application.classification.protocols.classification_rule_repository import (
    ClassificationRuleRepositoryProtocol,
)
from src.domain.classification.exceptions import ClassificationRuleNotFoundError
from src.domain.common.value_objects import ClassificationRuleId

logger = structlog.get_logger(__name__)


class DeleteRuleUseCase:
    """Delete a rule; receipt items keep their stamped snapshot."""

    def __init__(self, rule_repository: ClassificationRuleRepositoryProtocol) -> None:
        self.rule_repository = rule_repository

    async def delete_rule(self, rule_id: int) -> None:
        deleted = await self.rule_repository.delete(ClassificationRuleId(rule_id))
        if not deleted:
            raise ClassificationRuleNotFoundError(rule_id)
        logger.info("classification_rule_deleted", rule_id=rule_id)
