"""Configured roles of source accounts: personal cards vs the shared card.

Which account plays which role comes from configuration (ACCOUNT_ROLES_PATH),
never from hardcoded account names. An empty AccountRoles — a missing or
invalid config file — routes every source account as a personal card.

The configuration also maps the card's last four digits (read from the
receipt's `Kortti:` line) to the source account, so the card that paid picks
the account — see `source_account_for_card_digits`.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from src.domain.common.exceptions import ValidationError
from src.domain.common.value_object import ValueObject


class AccountRole(StrEnum):
    """The role a source account plays in ledger and CSV routing."""

    PERSONAL_CARD = "personal_card"
    SHARED_CARD = "shared_card"


@dataclass(frozen=True)
class AccountRoles(ValueObject):
    """The configured account roles plus the two special accounts.

    `purchase_for_flatmate` receives the positive postings of flatmate-only
    items (share 100%) bought on a personal card; `flatmate_expense_adjustment`
    receives their negative (contra) postings when bought on the shared card.
    """

    personal_cards: tuple[str, ...] = ()
    shared_card: str | None = None
    flatmate_expense_adjustment: str | None = None
    purchase_for_flatmate: str | None = None
    # Card last-4 digits -> source account, e.g. (("9841", "liabilities:...:gold"),).
    card_last_digits: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.shared_card is not None and self.flatmate_expense_adjustment is None:
            raise ValidationError(
                "A configured shared card needs the flatmate expense adjustment account",
                field="flatmate_expense_adjustment",
            )
        for digits, account in self.card_last_digits:
            if re.fullmatch(r"\d{4}", digits) is None or not account.strip():
                raise ValidationError(
                    f"Invalid card last digits {digits!r}: expected four digits "
                    "mapped to a source account",
                    field="card_last_digits",
                )

    def source_account_for_card_digits(self, digits: str | None) -> str | None:
        """The source account configured for these card digits, if any.

        Only the digits matter: `Kortti: MasterCard **** **** **** 9841` and
        `9841` both resolve to the account mapped to `9841`.
        """
        if not digits:
            return None
        key = re.sub(r"\D", "", digits)[-4:]
        return next((account for d, account in self.card_last_digits if d == key), None)

    def role_of(self, source_account: str | None) -> AccountRole:
        """The role of a source account; unconfigured accounts are personal cards."""
        if self.shared_card is not None and source_account == self.shared_card:
            return AccountRole.SHARED_CARD
        return AccountRole.PERSONAL_CARD

    def is_configured(self, source_account: str | None) -> bool:
        """Whether the source account has an explicit role in the configuration."""
        return source_account in self.personal_cards or source_account == self.shared_card
