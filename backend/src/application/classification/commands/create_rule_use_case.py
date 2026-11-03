"""Use case for creating a classification rule."""

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
from src.domain.classification.exceptions import DuplicateRulePatternError
from src.domain.classification.services.rule_engine import normalize_name

logger = structlog.get_logger(__name__)


class CreateRuleUseCase:
    """Validate and store a new rule.

    The expense account must be one of the ledger's expense accounts, and the
    normalized pattern must be unique (a DB constraint backs the check).
    """

    def __init__(
        self,
        rule_repository: ClassificationRuleRepositoryProtocol,
        ledger_service: LedgerServiceProtocol,
    ) -> None:
        self.rule_repository = rule_repository
        self.ledger_service = ledger_service

    async def create_rule(self, fields: RuleFields) -> ClassificationRule:
        await ensure_ledger_expense_account(self.ledger_service, fields.expense_account)
        normalized = normalize_name(fields.pattern)
        if await self.rule_repository.find_by_normalized_pattern(normalized) is not None:
            raise DuplicateRulePatternError(normalized)
        rule = ClassificationRule.create(
            pattern=fields.pattern,
            max_typos=fields.max_typos,
            expense_account=fields.expense_account,
            flatmate_share_override=fields.flatmate_share_override,
            enabled=fields.enabled,
        )
        saved = await self.rule_repository.save(rule)
        logger.info("classification_rule_created", rule_id=saved.id.value, pattern=fields.pattern)
        return saved
