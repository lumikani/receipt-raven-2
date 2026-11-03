"""Port to the configured source-account roles."""

from typing import Protocol

from src.domain.ledger.account_roles import AccountRoles


class AccountRolesProviderProtocol(Protocol):
    """Supplies the account roles; an absent or broken configuration means empty roles."""

    def load(self) -> AccountRoles: ...
