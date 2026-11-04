"""Classification domain exceptions."""

from src.domain.common.exceptions import ConflictError, EntityNotFoundError


class ClassificationRuleNotFoundError(EntityNotFoundError):
    """Raised when a classification rule cannot be found."""

    def __init__(self, rule_id: int) -> None:
        super().__init__("ClassificationRule", rule_id)
        self.rule_id = rule_id


class AccountShareDefaultNotFoundError(EntityNotFoundError):
    """Raised when an account has no share default."""

    def __init__(self, expense_account: str) -> None:
        super().__init__("AccountShareDefault", expense_account)
        self.expense_account = expense_account


class DuplicateRulePatternError(ConflictError):
    """Raised when a rule's normalized pattern already exists."""

    def __init__(self, normalized_pattern: str) -> None:
        super().__init__(
            f"A rule for '{normalized_pattern}' already exists",
            {"normalized_pattern": normalized_pattern},
        )
        self.normalized_pattern = normalized_pattern
