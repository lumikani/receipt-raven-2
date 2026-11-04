"""Read use case for the configured source-account roles.

The review screen needs the roles (and the unallocated account) to show the
routing preview and to flag source accounts without a configured role, so the
configuration is exposed here rather than hardcoded in the UI.
"""

from dataclasses import dataclass

from src.application.ledger.protocols.account_roles import AccountRolesProviderProtocol


@dataclass(frozen=True)
class AccountRolesView:
    """The account roles as the API exposes them, plus the unallocated account."""

    personal_cards: tuple[str, ...]
    shared_card: str | None
    flatmate_expense_adjustment: str | None
    purchase_for_flatmate: str | None
    unallocated_account: str


class GetAccountRolesUseCase:
    """Serve the configured account roles; an absent configuration means empty roles."""

    def __init__(
        self, account_roles: AccountRolesProviderProtocol, unallocated_account: str
    ) -> None:
        self.account_roles = account_roles
        self.unallocated_account = unallocated_account

    async def get_account_roles(self) -> AccountRolesView:
        roles = self.account_roles.load()
        return AccountRolesView(
            personal_cards=roles.personal_cards,
            shared_card=roles.shared_card,
            flatmate_expense_adjustment=roles.flatmate_expense_adjustment,
            purchase_for_flatmate=roles.purchase_for_flatmate,
            unallocated_account=self.unallocated_account,
        )
