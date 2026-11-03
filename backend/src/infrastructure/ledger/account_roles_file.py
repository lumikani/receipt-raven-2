"""Account roles read from a JSON file.

Format (the same as `config/account-roles.example.json`):

    {"personalCards": ["liabilities:op:credit-card:gold"],
     "sharedCard": "liabilities:personal:shared-account",
     "flatmateExpenseAdjustment": "expenses:flatmate-expense-adjustment",
     "purchaseForFlatmate": "expenses:purchase-for-flatmate"}

A missing or invalid file means empty roles: every source account is then
routed as a personal card.
"""

from pathlib import Path

import structlog
from pydantic import BaseModel, ValidationError

from src.domain.common.exceptions import ValidationError as DomainValidationError
from src.domain.ledger.account_roles import AccountRoles

logger = structlog.get_logger(__name__)


class _AccountRolesFile(BaseModel):
    personalCards: list[str]  # noqa: N815 - the file's field names
    sharedCard: str  # noqa: N815
    flatmateExpenseAdjustment: str  # noqa: N815
    purchaseForFlatmate: str  # noqa: N815


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
            roles = AccountRoles(
                personal_cards=tuple(card.strip() for card in parsed.personalCards if card.strip()),
                shared_card=parsed.sharedCard.strip(),
                flatmate_expense_adjustment=parsed.flatmateExpenseAdjustment.strip(),
                purchase_for_flatmate=parsed.purchaseForFlatmate.strip(),
            )
        except (OSError, UnicodeDecodeError, ValidationError, DomainValidationError) as exc:
            logger.error("account_roles_invalid", path=str(self.path), error=str(exc))
            return AccountRoles()
        logger.info(
            "account_roles_loaded",
            personal_cards=len(roles.personal_cards),
            shared_card=roles.shared_card,
        )
        return roles
