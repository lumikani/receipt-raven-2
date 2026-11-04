"""Unit tests for the AccountRoles value object: configured source-account roles."""

import pytest

from src.domain.common.exceptions import ValidationError
from src.domain.ledger.account_roles import AccountRole, AccountRoles

ROLES = AccountRoles(
    personal_cards=("liabilities:op:credit-card:gold", "liabilities:op:credit-card:duo"),
    shared_card="liabilities:personal:shared-account",
    flatmate_expense_adjustment="expenses:flatmate-expense-adjustment",
    purchase_for_flatmate="expenses:purchase-for-flatmate",
    card_last_digits=(
        ("1111", "liabilities:op:credit-card:gold"),
        ("2222", "liabilities:op:credit-card:duo"),
        ("0244", "liabilities:personal:shared-account"),
    ),
)


def test_configured_accounts_get_their_roles() -> None:
    assert ROLES.role_of("liabilities:op:credit-card:gold") is AccountRole.PERSONAL_CARD
    assert ROLES.role_of("liabilities:personal:shared-account") is AccountRole.SHARED_CARD


def test_unconfigured_source_account_defaults_to_the_personal_card_role() -> None:
    assert ROLES.role_of("Assets:Checking") is AccountRole.PERSONAL_CARD
    assert ROLES.role_of(None) is AccountRole.PERSONAL_CARD


def test_empty_roles_route_every_account_as_a_personal_card() -> None:
    empty = AccountRoles()

    assert empty.role_of("liabilities:personal:shared-account") is AccountRole.PERSONAL_CARD
    assert empty.role_of("anything") is AccountRole.PERSONAL_CARD
    assert empty.is_configured("anything") is False


def test_is_configured_covers_personal_cards_and_the_shared_card() -> None:
    assert ROLES.is_configured("liabilities:op:credit-card:duo") is True
    assert ROLES.is_configured("liabilities:personal:shared-account") is True
    assert ROLES.is_configured("Assets:Checking") is False


def test_a_shared_card_without_the_adjustment_account_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AccountRoles(shared_card="liabilities:personal:shared-account")


def test_card_last_digits_pick_the_source_account() -> None:
    assert ROLES.source_account_for_card_digits("1111") == "liabilities:op:credit-card:gold"
    assert ROLES.source_account_for_card_digits("0244") == "liabilities:personal:shared-account"


def test_card_digits_are_normalized_to_the_last_four_digits() -> None:
    assert ROLES.source_account_for_card_digits("**** 2222") == "liabilities:op:credit-card:duo"
    assert (
        ROLES.source_account_for_card_digits("MasterCard **** **** **** 2222")
        == "liabilities:op:credit-card:duo"
    )


def test_unknown_or_missing_card_digits_have_no_account() -> None:
    assert ROLES.source_account_for_card_digits("9999") is None
    assert ROLES.source_account_for_card_digits(None) is None
    assert ROLES.source_account_for_card_digits("") is None
    assert AccountRoles().source_account_for_card_digits("1111") is None


def test_card_last_digits_must_be_four_digits_mapped_to_an_account() -> None:
    with pytest.raises(ValidationError):
        AccountRoles(card_last_digits=(("123", "liabilities:op:credit-card:gold"),))
    with pytest.raises(ValidationError):
        AccountRoles(card_last_digits=(("abcd", "liabilities:op:credit-card:gold"),))
    with pytest.raises(ValidationError):
        AccountRoles(card_last_digits=(("1111", "  "),))
