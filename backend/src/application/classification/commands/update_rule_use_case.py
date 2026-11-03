"""Use case for editing a classification rule."""

import structlog

from src.application.classification.commands.rule_fields import (
    RuleFields,
    ensure_ledger_expense_account,
)
from src.application.classification.protocols.classification_rule_repository import (
    ClassificationRuleRepositoryProtocol,
)
from src.application.ledger.protocols.ledger_service import LedgerServiceProtocol
from src.domain.classification.entities.classification_rule import ClassificationRule
from src.domain.classification.exceptions import (
    ClassificationRuleNotFoundError,
    DuplicateRulePatternError,
)
from src.domain.classification.services.rule_engine import normalize_name
from src.domain.common.value_objects import ClassificationRuleId

logger = structlog.get_logger(__name__)


class UpdateRuleUseCase:
    """Replace a rule's editable fields, keeping its id and created_at."""

    def __init__(
        self,
        rule_repository: ClassificationRuleRepositoryProtocol,
        ledger_service: LedgerServiceProtocol,
    ) -> None:
        self.rule_repository = rule_repository
        self.ledger_service = ledger_service

    async def update_rule(self, rule_id: int, fields: RuleFields) -> ClassificationRule:
        rule = await self.rule_repository.find_by_id(ClassificationRuleId(rule_id))
        if rule is None:
            raise ClassificationRuleNotFoundError(rule_id)
        await ensure_ledger_expense_account(self.ledger_service, fields.expense_account)
        normalized = normalize_name(fields.pattern)
        existing = await self.rule_repository.find_by_normalized_pattern(normalized)
        if existing is not None and existing.id != rule.id:
            raise DuplicateRulePatternError(normalized)
        rule.update(
            pattern=fields.pattern,
            max_typos=fields.max_typos,
            expense_account=fields.expense_account,
            flatmate_share_override=fields.flatmate_share_override,
            enabled=fields.enabled,
        )
        saved = await self.rule_repository.save(rule)
        logger.info("classification_rule_updated", rule_id=saved.id.value)
        return saved
