"""API tests for the classification endpoints: rules CRUD and account share defaults.

Runs the real stack (HTTP client -> router -> use case -> repository) against a
fresh in-memory SQLite per test; the ledger is the FakeLedger, whose expense
accounts are Expenses:Groceries and Expenses:Clothes.
"""

from typing import Any

from httpx import AsyncClient

RULES = "/api/v1/classification/rules"
SHARE_DEFAULTS = "/api/v1/classification/account-share-defaults"


def rule_body(**overrides: object) -> dict[str, Any]:
    body: dict[str, Any] = {
        "pattern": "Banaani",
        "max_typos": 1,
        "expense_account": "Expenses:Groceries",
        "flatmate_share_override": None,
        "enabled": True,
    }
    body.update(overrides)
    return body


async def create_rule(client: AsyncClient, **overrides: object) -> dict[str, Any]:
    response = await client.post(RULES, json=rule_body(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


class TestRuleCrud:
    async def test_create_stores_the_rule_and_list_shows_it(self, client: AsyncClient) -> None:
        created = await create_rule(client, flatmate_share_override=25.0)

        assert created["id"] > 0
        assert created["pattern"] == "Banaani"
        assert created["normalized_pattern"] == "banaani"
        assert created["max_typos"] == 1
        assert created["expense_account"] == "Expenses:Groceries"
        assert created["flatmate_share_override"] == 25.0
        assert created["enabled"] is True
        assert created["created_at"]

        listing = (await client.get(RULES)).json()["items"]
        assert [r["id"] for r in listing] == [created["id"]]
        fetched = (await client.get(f"{RULES}/{created['id']}")).json()
        assert fetched == created

    async def test_create_defaults_max_typos_to_1(self, client: AsyncClient) -> None:
        body = rule_body()
        del body["max_typos"]
        response = await client.post(RULES, json=body)
        assert response.status_code == 201
        assert response.json()["max_typos"] == 1

    async def test_expense_account_must_be_a_ledger_expense_account(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(RULES, json=rule_body(expense_account="Expenses:Nope"))

        assert response.status_code == 400
        assert "not an expense account" in response.json()["message"]
        assert (await client.get(RULES)).json()["items"] == []

    async def test_max_typos_out_of_range_is_rejected(self, client: AsyncClient) -> None:
        for value in (-1, 3):
            response = await client.post(RULES, json=rule_body(max_typos=value))
            assert response.status_code == 422

    async def test_pattern_of_only_punctuation_is_rejected(self, client: AsyncClient) -> None:
        response = await client.post(RULES, json=rule_body(pattern="!!!"))

        assert response.status_code == 400
        assert "product name" in response.json()["message"]

    async def test_normalized_pattern_must_be_unique(self, client: AsyncClient) -> None:
        await create_rule(client, pattern="Banaani")

        response = await client.post(RULES, json=rule_body(pattern="banaani 2 kpl !!!"))

        assert response.status_code == 409
        assert len((await client.get(RULES)).json()["items"]) == 1

    async def test_update_replaces_the_fields(self, client: AsyncClient) -> None:
        created = await create_rule(client)

        response = await client.put(
            f"{RULES}/{created['id']}",
            json=rule_body(
                pattern="Kellogg's Corn Flakes 500g",
                max_typos=2,
                expense_account="Expenses:Groceries",
                flatmate_share_override=80.0,
                enabled=False,
            ),
        )

        assert response.status_code == 200
        updated = response.json()
        assert updated["id"] == created["id"]
        assert updated["pattern"] == "Kellogg's Corn Flakes 500g"
        assert updated["normalized_pattern"] == "kellogg s corn flakes 500g"
        assert updated["max_typos"] == 2
        assert updated["flatmate_share_override"] == 80.0
        assert updated["enabled"] is False
        assert updated["created_at"] == created["created_at"]

    async def test_update_to_an_existing_pattern_conflicts(self, client: AsyncClient) -> None:
        await create_rule(client, pattern="Maito")
        other = await create_rule(client, pattern="Leipä")

        response = await client.put(f"{RULES}/{other['id']}", json=rule_body(pattern="maito"))

        assert response.status_code == 409

    async def test_update_of_a_missing_rule_is_404(self, client: AsyncClient) -> None:
        response = await client.put(f"{RULES}/999", json=rule_body())
        assert response.status_code == 404

    async def test_enable_and_disable(self, client: AsyncClient) -> None:
        created = await create_rule(client)

        disabled = (
            await client.post(f"{RULES}/{created['id']}/set-enabled", json={"enabled": False})
        ).json()
        assert disabled["enabled"] is False
        assert disabled["pattern"] == created["pattern"]

        enabled = (
            await client.post(f"{RULES}/{created['id']}/set-enabled", json={"enabled": True})
        ).json()
        assert enabled["enabled"] is True

        assert (
            await client.post(f"{RULES}/999/set-enabled", json={"enabled": False})
        ).status_code == 404

    async def test_delete_removes_the_rule(self, client: AsyncClient) -> None:
        created = await create_rule(client)

        response = await client.delete(f"{RULES}/{created['id']}")

        assert response.status_code == 204
        assert (await client.get(f"{RULES}/{created['id']}")).status_code == 404
        assert (await client.get(RULES)).json()["items"] == []
        assert (await client.delete(f"{RULES}/{created['id']}")).status_code == 404


class TestAccountShareDefaults:
    async def test_upsert_create_then_update(self, client: AsyncClient) -> None:
        created = (
            await client.put(
                SHARE_DEFAULTS, json={"expense_account": "Expenses:Groceries", "share": 25}
            )
        ).json()
        assert created["expense_account"] == "Expenses:Groceries"
        assert created["share"] == 25.0

        updated_response = await client.put(
            SHARE_DEFAULTS, json={"expense_account": "Expenses:Groceries", "share": 50}
        )
        assert updated_response.status_code == 200
        updated = updated_response.json()
        assert updated["id"] == created["id"]  # same row, not a duplicate
        assert updated["share"] == 50.0

        listing = (await client.get(SHARE_DEFAULTS)).json()["items"]
        assert listing == [updated]

    async def test_share_out_of_range_is_rejected(self, client: AsyncClient) -> None:
        for share in (-1, 101):
            response = await client.put(
                SHARE_DEFAULTS, json={"expense_account": "Expenses:Groceries", "share": share}
            )
            assert response.status_code == 422

    async def test_account_must_be_a_ledger_expense_account(self, client: AsyncClient) -> None:
        response = await client.put(
            SHARE_DEFAULTS, json={"expense_account": "Expenses:Nope", "share": 10}
        )

        assert response.status_code == 400
        assert "not an expense account" in response.json()["message"]
        assert (await client.get(SHARE_DEFAULTS)).json()["items"] == []

    async def test_delete(self, client: AsyncClient) -> None:
        await client.put(SHARE_DEFAULTS, json={"expense_account": "Expenses:Clothes", "share": 10})

        response = await client.delete(f"{SHARE_DEFAULTS}/Expenses:Clothes")

        assert response.status_code == 204
        assert (await client.get(SHARE_DEFAULTS)).json()["items"] == []
        assert (await client.delete(f"{SHARE_DEFAULTS}/Expenses:Clothes")).status_code == 404
