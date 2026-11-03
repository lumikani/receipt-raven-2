"""API tests for classification in the analysis pipeline: stamping, pre-fill,
re-classification and manual-override semantics.

Runs the real stack (HTTP client -> router -> use case -> repository) against a
fresh in-memory SQLite per test; the ledger and the AI model are the fakes in
`tests/fakes.py`. The unallocated account is the settings default
`expenses:unallocated`.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from httpx import AsyncClient

from src.domain.jobs.entities.receipt_job import ReceiptJob
from tests.fakes import FakeLedger, FakeReceiptAnalyzer, analysis

JOBS = "/api/v1/jobs"
RECEIPTS = "/api/v1/receipts"
RULES = "/api/v1/classification/rules"
SHARE_DEFAULTS = "/api/v1/classification/account-share-defaults"
PHOTO = b"\xff\xd8\xff\xe0 fake jpeg"

RunWorker = Callable[[], Awaitable[ReceiptJob | None]]


async def upload(client: AsyncClient) -> dict[str, Any]:
    response = await client.post(JOBS, files={"file": ("capture.jpg", PHOTO, "image/jpeg")})
    assert response.status_code == 201, response.text
    return response.json()


async def only_receipt(client: AsyncClient) -> dict[str, Any]:
    [summary] = (await client.get(RECEIPTS)).json()["items"]
    return (await client.get(f"{RECEIPTS}/{summary['id']}")).json()


async def create_rule(client: AsyncClient, **overrides: object) -> dict[str, Any]:
    body: dict[str, Any] = {
        "pattern": "Banaani",
        "max_typos": 1,
        "expense_account": "Expenses:Groceries",
        "flatmate_share_override": 50.0,
        "enabled": True,
    }
    body.update(overrides)
    response = await client.post(RULES, json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def set_share_default(client: AsyncClient, account: str, share: float) -> None:
    response = await client.put(SHARE_DEFAULTS, json={"expense_account": account, "share": share})
    assert response.status_code == 200, response.text


def receipt_body(**overrides: object) -> dict[str, Any]:
    body: dict[str, Any] = {
        "payee": "Prisma",
        "source_account": "Assets:Checking",
        "date": "2026-10-01",
        "total_sum": 12.5,
        "currency": "EUR",
        "items": [
            {"name": "Maito", "expense_account": "Expenses:Groceries", "price": 2.5},
            {"name": "Leipä", "expense_account": "Expenses:Groceries", "price": 3.0},
            {"name": "Sukat", "expense_account": "Expenses:Clothes", "price": 7.0},
        ],
    }
    body.update(overrides)
    return body


async def create_receipt(client: AsyncClient, **overrides: object) -> dict[str, Any]:
    response = await client.post(RECEIPTS, json=receipt_body(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


class TestAnalysisStamping:
    """The rule engine stamps every analysed item, for every provider."""

    async def test_a_matching_rule_beats_the_llm_account(
        self, client: AsyncClient, run_worker: RunWorker
    ) -> None:
        rule = await create_rule(client, flatmate_share_override=50.0)
        await set_share_default(client, "Expenses:Clothes", 25.0)
        await upload(client)

        await run_worker()

        receipt = await only_receipt(client)
        banaani, tpaita = receipt["items"]
        assert banaani["name"] == "Banaani"
        assert (
            banaani["expense_account"],
            banaani["flatmate_share"],
            banaani["matched_rule_id"],
        ) == ("Expenses:Groceries", 50.0, rule["id"])
        assert banaani["classification_overridden"] is False
        # No rule for the T-paita: the LLM-chosen account stays, with its default share.
        assert (
            tpaita["expense_account"],
            tpaita["flatmate_share"],
            tpaita["matched_rule_id"],
        ) == ("Expenses:Clothes", 25.0, None)

    async def test_local_provider_unmatched_items_land_on_unallocated(
        self, client: AsyncClient, run_worker: RunWorker, analyzer: FakeReceiptAnalyzer
    ) -> None:
        # The local parser emits an empty expense account for every item.
        await create_rule(client, flatmate_share_override=50.0)
        analyzer.result = analysis(products=(("Banaani", "", 0.8), ("Höylä", "", 2.0)), total=2.8)
        await upload(client)

        await run_worker()

        banaani, hoyla = (await only_receipt(client))["items"]
        assert banaani["expense_account"] == "Expenses:Groceries"
        assert banaani["matched_rule_id"] is not None
        assert hoyla["expense_account"] == "expenses:unallocated"
        assert hoyla["flatmate_share"] == 0.0
        assert hoyla["matched_rule_id"] is None

    async def test_card_last_digits_from_the_analysis_are_persisted(
        self, client: AsyncClient, run_worker: RunWorker, analyzer: FakeReceiptAnalyzer
    ) -> None:
        analyzer.result = analysis(card_last_digits="4321")
        await upload(client)

        await run_worker()

        assert (await only_receipt(client))["card_last_digits"] == "4321"


class TestManualPrefill:
    """Hand-entered receipts are rule-pre-filled at creation too."""

    async def test_a_matching_rule_stamps_the_item_at_creation(self, client: AsyncClient) -> None:
        rule = await create_rule(client, flatmate_share_override=50.0)
        body = receipt_body(
            items=[
                {"name": "Banaani 2 kpl", "expense_account": "", "price": 2.5},
                {"name": "Sukat", "expense_account": "Expenses:Clothes", "price": 10.0},
            ],
            total_sum=12.5,
        )

        response = await client.post(RECEIPTS, json=body)

        assert response.status_code == 201, response.text
        banaani, sukat = response.json()["items"]
        assert (
            banaani["expense_account"],
            banaani["flatmate_share"],
            banaani["matched_rule_id"],
        ) == ("Expenses:Groceries", 50.0, rule["id"])
        # No rule for Sukat: the entered account stays, with its share default (none: 0%).
        assert (sukat["expense_account"], sukat["flatmate_share"], sukat["matched_rule_id"]) == (
            "Expenses:Clothes",
            0.0,
            None,
        )
        assert response.json()["card_last_digits"] is None

    async def test_existing_receipts_are_not_retroactively_reclassified(
        self, client: AsyncClient, run_worker: RunWorker
    ) -> None:
        await upload(client)
        await run_worker()
        await create_rule(client)  # the rule appears only after the analysis ran

        banaani = (await only_receipt(client))["items"][0]

        assert banaani["name"] == "Banaani"
        assert banaani["expense_account"] == "Expenses:Groceries"  # the analyzer's choice
        assert banaani["matched_rule_id"] is None  # no retroactive stamping


class TestReclassify:
    """Manual re-classification: per receipt and bulk over the unapproved."""

    async def test_per_receipt_reclassify_applies_the_current_rules(
        self, client: AsyncClient
    ) -> None:
        created = await create_receipt(
            client,
            items=[
                {"name": "Maito", "expense_account": "Expenses:Groceries", "price": 2.5},
                {"name": "Leipä", "expense_account": "", "price": 3.0},
                {"name": "Sukat", "expense_account": "Expenses:Clothes", "price": 7.0},
            ],
        )
        rule = await create_rule(
            client,
            pattern="Maito",
            expense_account="Expenses:Clothes",
            flatmate_share_override=100.0,
        )

        response = await client.post(f"{RECEIPTS}/{created['id']}/reclassify")

        assert response.status_code == 200, response.text
        items = {item["name"]: item for item in response.json()["items"]}
        assert (
            items["Maito"]["expense_account"],
            items["Maito"]["flatmate_share"],
            items["Maito"]["matched_rule_id"],
        ) == ("Expenses:Clothes", 100.0, rule["id"])
        # No rule for the other items: their accounts stay as they were.
        assert items["Sukat"]["expense_account"] == "Expenses:Clothes"
        assert items["Sukat"]["matched_rule_id"] is None
        assert items["Leipä"]["expense_account"] == "expenses:unallocated"

    async def test_bulk_reclassifies_only_the_unapproved_receipts(
        self, client: AsyncClient, ledger: FakeLedger
    ) -> None:
        first = await create_receipt(client, payee="One")
        second = await create_receipt(client, payee="Two")
        approved = await create_receipt(client, payee="Three")
        await client.post(f"{RECEIPTS}/{approved['id']}/approve", json=receipt_body(payee="Three"))
        rule = await create_rule(client, pattern="Maito", flatmate_share_override=100.0)

        response = await client.post(f"{RECEIPTS}/reclassify-all-unapproved")

        assert response.status_code == 200, response.text
        assert sorted(response.json()["receipt_ids"]) == sorted([first["id"], second["id"]])
        for receipt_id in (first["id"], second["id"]):
            fetched = (await client.get(f"{RECEIPTS}/{receipt_id}")).json()
            maito = next(i for i in fetched["items"] if i["name"] == "Maito")
            assert maito["matched_rule_id"] == rule["id"]
        approved_after = (await client.get(f"{RECEIPTS}/{approved['id']}")).json()
        assert all(item["matched_rule_id"] is None for item in approved_after["items"])

    async def test_reclassify_skips_manual_overrides_but_not_ocr_fixes(
        self, client: AsyncClient, ledger: FakeLedger
    ) -> None:
        created = await create_receipt(client)
        items = {item["name"]: item for item in created["items"]}
        # A rejected approve persists the edits but leaves the receipt unapproved.
        ledger.reject_with = "ledger says no"
        await client.post(
            f"{RECEIPTS}/{created['id']}/approve",
            json=receipt_body(
                items=[
                    {
                        **items["Maito"],
                        "expense_account": "Expenses:Clothes",
                        "flatmate_share": 80.0,
                    },
                    {**items["Leipä"], "name": "Leipä 400g"},  # name edit = OCR fix
                    {**items["Sukat"]},
                ]
            ),
        )
        fetched = (await client.get(f"{RECEIPTS}/{created['id']}")).json()
        by_name = {item["name"]: item for item in fetched["items"]}
        assert by_name["Maito"]["classification_overridden"] is True
        assert by_name["Maito"]["matched_rule_id"] is None
        assert by_name["Leipä 400g"]["classification_overridden"] is False
        ledger.reject_with = None
        await create_rule(client, pattern="Maito", expense_account="Expenses:Groceries")
        leipa_rule = await create_rule(
            client,
            pattern="Leipä 400g",
            expense_account="Expenses:Groceries",
            flatmate_share_override=10.0,
        )

        response = await client.post(f"{RECEIPTS}/{created['id']}/reclassify")

        assert response.status_code == 200, response.text
        by_name = {item["name"]: item for item in response.json()["items"]}
        # The manual override survives re-classification.
        assert (
            by_name["Maito"]["expense_account"],
            by_name["Maito"]["flatmate_share"],
            by_name["Maito"]["matched_rule_id"],
        ) == ("Expenses:Clothes", 80.0, None)
        assert by_name["Maito"]["classification_overridden"] is True
        # The OCR-fixed name re-classified under its rule.
        assert by_name["Leipä 400g"]["matched_rule_id"] == leipa_rule["id"]
        assert by_name["Leipä 400g"]["flatmate_share"] == 10.0

    async def test_an_approved_receipt_cannot_be_reclassified(self, client: AsyncClient) -> None:
        created = await create_receipt(client)
        await client.post(f"{RECEIPTS}/{created['id']}/approve", json=receipt_body())
        await create_rule(client)

        response = await client.post(f"{RECEIPTS}/{created['id']}/reclassify")

        assert response.status_code == 400
        assert "already approved" in response.json()["message"]
        fetched = (await client.get(f"{RECEIPTS}/{created['id']}")).json()
        assert all(item["matched_rule_id"] is None for item in fetched["items"])

    async def test_unknown_receipt_is_not_found(self, client: AsyncClient) -> None:
        assert (await client.post(f"{RECEIPTS}/999/reclassify")).status_code == 404
        assert (await client.post(f"{RECEIPTS}/reclassify-all-unapproved")).status_code == 200
