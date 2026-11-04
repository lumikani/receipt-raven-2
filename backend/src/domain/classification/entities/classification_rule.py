"""Classification rule aggregate: one product pattern → expense account (+ share)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.classification.services.rule_engine import normalize_name
from src.domain.common.aggregate_root import AggregateRoot
from src.domain.common.exceptions import ValidationError
from src.domain.common.value_objects import ClassificationRuleId, check_share

MAX_TYPOS_LIMIT = 2


def _check_share_override(value: float | None, field_name: str) -> None:
    if value is not None:
        check_share(value, field_name)


@dataclass(eq=False)
class ClassificationRule(AggregateRoot[ClassificationRuleId]):
    """Maps a normalized product name to an expense account.

    `pattern` is the full normalized product name as the user writes it; its
    normalized form is unique per rule (DB constraint) and what matching uses.
    `max_typos` 0-2 (default 1; 0 = exact match only). `flatmate_share_override`
    beats the account's share default when set.
    """

    id: ClassificationRuleId
    pattern: str
    max_typos: int
    expense_account: str
    flatmate_share_override: float | None = None
    enabled: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    normalized_pattern: str = field(init=False)

    def __post_init__(self) -> None:
        self.pattern = self.pattern.strip()
        if not self.pattern:
            raise ValidationError("Rule pattern cannot be empty", field="pattern")
        if not 0 <= self.max_typos <= MAX_TYPOS_LIMIT:
            raise ValidationError(
                f"max_typos must be between 0 and {MAX_TYPOS_LIMIT}",
                field="max_typos",
                value=self.max_typos,
            )
        self.expense_account = self.expense_account.strip()
        if not self.expense_account:
            raise ValidationError("Expense account cannot be empty", field="expense_account")
        _check_share_override(self.flatmate_share_override, "flatmate_share_override")
        self.normalized_pattern = normalize_name(self.pattern)
        if not self.normalized_pattern:
            raise ValidationError(
                "Rule pattern must contain a product name", field="pattern", value=self.pattern
            )

    @classmethod
    def create(
        cls,
        *,
        pattern: str,
        expense_account: str,
        max_typos: int = 1,
        flatmate_share_override: float | None = None,
        enabled: bool = True,
    ) -> ClassificationRule:
        """A new rule (id 0, until stored)."""
        return cls(
            id=ClassificationRuleId.generate(),
            pattern=pattern,
            max_typos=max_typos,
            expense_account=expense_account,
            flatmate_share_override=flatmate_share_override,
            enabled=enabled,
        )

    @classmethod
    def create_with_id(
        cls,
        *,
        id: ClassificationRuleId,
        pattern: str,
        max_typos: int,
        expense_account: str,
        flatmate_share_override: float | None,
        enabled: bool,
        created_at: datetime,
    ) -> ClassificationRule:
        """Reconstitute a stored rule."""
        return cls(
            id=id,
            pattern=pattern,
            max_typos=max_typos,
            expense_account=expense_account,
            flatmate_share_override=flatmate_share_override,
            enabled=enabled,
            created_at=created_at,
        )

    def update(
        self,
        *,
        pattern: str,
        max_typos: int,
        expense_account: str,
        flatmate_share_override: float | None,
        enabled: bool,
    ) -> None:
        """Replace every editable field, re-validating the invariants."""
        candidate = ClassificationRule.create_with_id(
            id=self.id,
            pattern=pattern,
            max_typos=max_typos,
            expense_account=expense_account,
            flatmate_share_override=flatmate_share_override,
            enabled=enabled,
            created_at=self.created_at,
        )
        self.pattern = candidate.pattern
        self.normalized_pattern = candidate.normalized_pattern
        self.max_typos = candidate.max_typos
        self.expense_account = candidate.expense_account
        self.flatmate_share_override = candidate.flatmate_share_override
        self.enabled = candidate.enabled

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
