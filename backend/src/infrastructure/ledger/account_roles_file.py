"""Account roles read from a JSON file.

Format (the same as `config/account-roles.example.json`):

    {"personalCards": ["liabilities:op:credit-card:gold"],
     "sharedCard": "liabilities:personal:shared-account",
     "flatmateExpenseAdjustment": "expenses:flatmate-expense-adjustment",
     "purchaseForFlatmate": "expenses:purchase-for-flatmate",
     "cardLastDigits": {"9841": "liabilities:op:credit-card:gold"}}

`cardLastDigits` maps the card's last four digits (read from the receipt's
`Kortti:` line) to the source account, so the card that paid picks the
account. It is optional.

A missing or invalid file means empty roles: every source account is then
routed as a personal card.
"""

import re
from pathlib import Path

import structlog
from pydantic import BaseModel, Field, ValidationError

from src.domain.common.exceptions import ValidationError as DomainValidationError
from src.domain.ledger.account_roles import AccountRoles

logger = structlog.get_logger(__name__)


class _AccountRolesFile(BaseModel):
    personalCards: list[str]  # noqa: N815 - the file's field names
    sharedCard: str  # noqa: N815
    flatmateExpenseAdjustment: str  # noqa: N815
    purchaseForFlatmate: str  # noqa: N815
    cardLastDigits: dict[str, str] = Field(default_factory=dict)  # noqa: N815


class AccountRolesFile:
    """Loads the roles once; a missing or invalid file means empty roles."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._roles: AccountRoles | None = None

    def load(self) -> AccountRoles:
        if self._roles is None:
            self._roles = self._read()
        return self._roles

    def _read(self) -> AccountRoles:
        if not self.path.is_file():
            logger.info("account_roles_not_found", path=str(self.path))
            return AccountRoles()
        try:
            parsed = _AccountRolesFile.model_validate_json(self.path.read_text(encoding="utf-8"))
            card_last_digits = []
            for raw_digits, raw_account in parsed.cardLastDigits.items():
                digits, account = raw_digits.strip(), raw_account.strip()
                if re.fullmatch(r"\d{4}", digits) and account:
                    card_last_digits.append((digits, account))
                else:
                    logger.warning(
                        "account_roles_card_entry_skipped", digits=digits, account=account
                    )
            roles = AccountRoles(
                personal_cards=tuple(card.strip() for card in parsed.personalCards if card.strip()),
                shared_card=parsed.sharedCard.strip(),
                flatmate_expense_adjustment=parsed.flatmateExpenseAdjustment.strip(),
                purchase_for_flatmate=parsed.purchaseForFlatmate.strip(),
                card_last_digits=tuple(card_last_digits),
            )
        except (OSError, UnicodeDecodeError, ValidationError, DomainValidationError) as exc:
            logger.error("account_roles_invalid", path=str(self.path), error=str(exc))
            return AccountRoles()
        logger.info(
            "account_roles_loaded",
            personal_cards=len(roles.personal_cards),
            shared_card=roles.shared_card,
            card_last_digits=len(roles.card_last_digits),
        )
        return roles
