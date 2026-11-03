"""Unit tests for the AccountRoles value object: configured source-account roles."""

import pytest

from src.domain.common.exceptions import ValidationError
from src.domain.ledger.account_roles import AccountRole, AccountRoles

ROLES = AccountRoles(
    personal_cards=("liabilities:op:credit-card:gold", "liabilities:op:credit-card:duo"),
    shared_card="liabilities:personal:shared-account",
    flatmate_expense_adjustment="expenses:flatmate-expense-adjustment",
    purchase_for_flatmate="expenses:purchase-for-flatmate",
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
