"""Port for storing ClassificationRule aggregates."""

from typing import Protocol

from src.domain.classification.entities.classification_rule import ClassificationRule
from src.domain.common.value_objects import ClassificationRuleId


class ClassificationRuleRepositoryProtocol(Protocol):
    """Load and store classification rules."""

    async def find_by_id(self, rule_id: ClassificationRuleId, /) -> ClassificationRule | None:
        """Return the rule, or ``None`` when there is no such rule."""
        ...

    async def find_all(self) -> list[ClassificationRule]:
        """Every rule, oldest first (the fuzzy tie-break order)."""
        ...

    async def find_by_normalized_pattern(
        self, normalized_pattern: str
    ) -> ClassificationRule | None:
        """Return the rule with this normalized pattern, if any."""
        ...

    async def save(self, rule: ClassificationRule, /) -> ClassificationRule:
        """Insert a new rule (id 0) or update an existing one."""
        ...

    async def delete(self, rule_id: ClassificationRuleId, /) -> bool:
        """Delete a rule. Returns False if there was no such rule."""
        ...
