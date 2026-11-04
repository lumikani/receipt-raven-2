"""Account share default aggregate: an expense account's default flatmate share."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.common.aggregate_root import AggregateRoot
from src.domain.common.exceptions import ValidationError
from src.domain.common.value_objects import AccountShareDefaultId, check_share


@dataclass(eq=False)
class AccountShareDefault(AggregateRoot[AccountShareDefaultId]):
    """The default flatmate share (0-100) for one expense account.

    One row per expense account (unique constraint). A rule's share override
    beats this default; a missing default means 0% and the item is flagged.
    """

    id: AccountShareDefaultId
    expense_account: str
    share: float
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.expense_account = self.expense_account.strip()
        if not self.expense_account:
            raise ValidationError("Expense account cannot be empty", field="expense_account")
        check_share(self.share, "share")

    @classmethod
    def create(cls, *, expense_account: str, share: float) -> AccountShareDefault:
        """A new default (id 0, until stored)."""
        return cls(
            id=AccountShareDefaultId.generate(), expense_account=expense_account, share=share
        )

    @classmethod
    def create_with_id(
        cls, *, id: AccountShareDefaultId, expense_account: str, share: float, created_at: datetime
    ) -> AccountShareDefault:
        """Reconstitute a stored default."""
        return cls(id=id, expense_account=expense_account, share=share, created_at=created_at)

    def update(self, *, share: float) -> None:
        check_share(share, "share")
        self.share = share
