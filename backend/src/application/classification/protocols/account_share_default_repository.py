"""Port for storing AccountShareDefault aggregates."""

from typing import Protocol

from src.domain.classification.entities.account_share_default import AccountShareDefault
from src.domain.common.value_objects import AccountShareDefaultId


class AccountShareDefaultRepositoryProtocol(Protocol):
    """Load and store per-account flatmate share defaults."""

    async def find_all(self) -> list[AccountShareDefault]:
        """Every default, ordered by expense account."""
        ...

    async def find_by_account(self, expense_account: str) -> AccountShareDefault | None:
        """Return the account's default, or ``None`` when it has none."""
        ...

    async def save(self, default: AccountShareDefault, /) -> AccountShareDefault:
        """Insert a new default (id 0) or update an existing one."""
        ...

    async def delete(self, default_id: AccountShareDefaultId, /) -> bool:
        """Delete a default. Returns False if there was no such default."""
        ...
