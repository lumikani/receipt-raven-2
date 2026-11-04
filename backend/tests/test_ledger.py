"""API tests for reading the ledger's accounts, payees and account roles."""

from httpx import AsyncClient

from src.domain.ledger.account_roles import AccountRoles
from tests.fakes import FakeAccountRoles, FakeLedger

LEDGER = "/api/v1/ledger"


async def test_lists_accounts_of_the_requested_types(client: AsyncClient) -> None:
    response = await client.get(
        f"{LEDGER}/accounts", params=[("type", "Assets"), ("type", "Liabilities")]
    )

    assert response.status_code == 200
    assert response.json()["items"] == [
        {"name": "Assets:Checking", "type": "Assets"},
        {"name": "Liabilities:CreditCard", "type": "Liabilities"},
    ]


async def test_lists_every_account_without_a_type(client: AsyncClient) -> None:
    response = await client.get(f"{LEDGER}/accounts")

    assert len(response.json()["items"]) == 5


async def test_lists_payees_sorted_without_duplicates(client: AsyncClient) -> None:
    response = await client.get(f"{LEDGER}/payees")

    assert response.json()["items"] == ["Alko", "K-Market", "Prisma"]


async def test_unavailable_ledger_is_a_bad_gateway(client: AsyncClient, ledger: FakeLedger) -> None:
    ledger.unavailable = True

    response = await client.get(f"{LEDGER}/accounts")

    assert response.status_code == 502
    assert response.json()["error"] == "bad_gateway"


async def test_account_roles_default_to_empty_with_the_unallocated_account(
    client: AsyncClient,
) -> None:
    response = await client.get(f"{LEDGER}/account-roles")

    assert response.status_code == 200
    assert response.json() == {
        "personal_cards": [],
        "shared_card": None,
        "flatmate_expense_adjustment": None,
        "purchase_for_flatmate": None,
        "unallocated_account": "expenses:unallocated",
    }


async def test_account_roles_come_from_the_configuration(
    client: AsyncClient, account_roles: FakeAccountRoles
) -> None:
    account_roles.roles = AccountRoles(
        personal_cards=("liabilities:op:credit-card:gold",),
        shared_card="liabilities:personal:shared-account",
        flatmate_expense_adjustment="expenses:flatmate-expense-adjustment",
        purchase_for_flatmate="expenses:purchase-for-flatmate",
    )

    response = await client.get(f"{LEDGER}/account-roles")

    assert response.status_code == 200
    assert response.json() == {
        "personal_cards": ["liabilities:op:credit-card:gold"],
        "shared_card": "liabilities:personal:shared-account",
        "flatmate_expense_adjustment": "expenses:flatmate-expense-adjustment",
        "purchase_for_flatmate": "expenses:purchase-for-flatmate",
        "unallocated_account": "expenses:unallocated",
    }
