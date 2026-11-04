"""Unit tests for the AccountRolesFile provider: load-once JSON config."""

from pathlib import Path

from src.domain.ledger.account_roles import AccountRole, AccountRoles
from src.infrastructure.ledger.account_roles_file import AccountRolesFile

VALID = """
{
  "personalCards": ["liabilities:op:credit-card:gold", "liabilities:op:credit-card:duo"],
  "sharedCard": "liabilities:personal:shared-account",
  "flatmateExpenseAdjustment": "expenses:flatmate-expense-adjustment",
  "purchaseForFlatmate": "expenses:purchase-for-flatmate",
  "cardLastDigits": {
    "1111": "liabilities:op:credit-card:gold",
    "0244": "liabilities:personal:shared-account"
  }
}
"""


def write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "account-roles.json"
    path.write_text(content, encoding="utf-8")
    return path


def test_missing_file_means_empty_roles_and_every_account_is_a_personal_card(
    tmp_path: Path,
) -> None:
    roles = AccountRolesFile(tmp_path / "nope.json").load()

    assert roles == AccountRoles()
    assert roles.role_of("liabilities:personal:shared-account") is AccountRole.PERSONAL_CARD


def test_invalid_json_means_empty_roles(tmp_path: Path) -> None:
    assert AccountRolesFile(write(tmp_path, "{not json")).load() == AccountRoles()


def test_a_file_with_a_missing_key_is_invalid_and_means_empty_roles(tmp_path: Path) -> None:
    path = write(tmp_path, '{"personalCards": ["liabilities:op:credit-card:gold"]}')

    assert AccountRolesFile(path).load() == AccountRoles()


def test_a_file_that_is_not_utf8_means_empty_roles(tmp_path: Path) -> None:
    path = tmp_path / "account-roles.json"
    path.write_bytes(b"\xff\xfe not utf-8")

    assert AccountRolesFile(path).load() == AccountRoles()


def test_valid_file_loads_the_roles_once(tmp_path: Path) -> None:
    loader = AccountRolesFile(write(tmp_path, VALID))

    roles = loader.load()

    assert roles.personal_cards == (
        "liabilities:op:credit-card:gold",
        "liabilities:op:credit-card:duo",
    )
    assert roles.shared_card == "liabilities:personal:shared-account"
    assert roles.flatmate_expense_adjustment == "expenses:flatmate-expense-adjustment"
    assert roles.purchase_for_flatmate == "expenses:purchase-for-flatmate"
    assert roles.role_of("liabilities:personal:shared-account") is AccountRole.SHARED_CARD
    assert roles.role_of("liabilities:op:credit-card:gold") is AccountRole.PERSONAL_CARD
    assert roles.source_account_for_card_digits("1111") == "liabilities:op:credit-card:gold"
    assert roles.source_account_for_card_digits("0244") == "liabilities:personal:shared-account"
    assert roles.source_account_for_card_digits("9999") is None
    assert loader.load() is roles


def test_card_last_digits_are_optional(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        {
          "personalCards": ["liabilities:op:credit-card:gold"],
          "sharedCard": "liabilities:personal:shared-account",
          "flatmateExpenseAdjustment": "expenses:flatmate-expense-adjustment",
          "purchaseForFlatmate": "expenses:purchase-for-flatmate"
        }
        """,
    )

    roles = AccountRolesFile(path).load()

    assert roles.card_last_digits == ()
    assert roles.source_account_for_card_digits("1111") is None


def test_invalid_card_last_digits_entries_are_skipped_not_fatal(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
        {
          "personalCards": ["liabilities:op:credit-card:gold"],
          "sharedCard": "liabilities:personal:shared-account",
          "flatmateExpenseAdjustment": "expenses:flatmate-expense-adjustment",
          "purchaseForFlatmate": "expenses:purchase-for-flatmate",
          "cardLastDigits": {
            "12": "liabilities:op:credit-card:duo",
            "": "liabilities:op:credit-card:duo",
            "1111": "liabilities:op:credit-card:gold"
          }
        }
        """,
    )

    roles = AccountRolesFile(path).load()

    assert roles.card_last_digits == (("1111", "liabilities:op:credit-card:gold"),)
    assert roles.source_account_for_card_digits("1111") == "liabilities:op:credit-card:gold"
    assert roles.source_account_for_card_digits("12") is None
    assert roles.shared_card == "liabilities:personal:shared-account"
