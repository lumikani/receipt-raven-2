"""API tests for the receipts endpoints: entry by hand, listing, approval, deletion."""

from typing import Any

from httpx import AsyncClient

from src.domain.ledger.account_roles import AccountRoles
from tests.fakes import FakeAccountRoles, FakeLedger

RECEIPTS = "/api/v1/receipts"

SHARED_ROLES = AccountRoles(
    personal_cards=("Assets:Checking",),
    shared_card="Liabilities:Shared",
    flatmate_expense_adjustment="Expenses:FlatmateAdjustment",
    purchase_for_flatmate="Expenses:PurchaseForFlatmate",
)


def receipt_body(**overrides: object) -> dict[str, Any]:
    body: dict[str, Any] = {
        "payee": "Prisma",
        "description": "Ruokaostokset",
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


class TestCreateReceipt:
    async def test_stores_an_unapproved_receipt_entered_by_hand(self, client: AsyncClient) -> None:
        created = await create_receipt(client, payee="  Prisma  ")

        fetched = (await client.get(f"{RECEIPTS}/{created['id']}")).json()
        assert fetched["payee"] == "Prisma"
        assert fetched["status"] == "unapproved"
        assert fetched["parsed_by"] == "user"
        assert fetched["date"] == "2026-10-01"
        assert fetched["ocr_notes"] is None
        assert fetched["document"] is None
        assert [(i["name"], i["price"]) for i in fetched["items"]] == [
            ("Maito", 2.5),
            ("Leipä", 3.0),
            ("Sukat", 7.0),
        ]

    async def test_rejects_a_blank_payee_with_a_readable_message(self, client: AsyncClient) -> None:
        response = await client.post(RECEIPTS, json=receipt_body(payee="   "))

        assert response.status_code == 400
        assert response.json() == {"error": "bad_request", "message": "Payee cannot be empty"}

    async def test_requires_at_least_one_item(self, client: AsyncClient) -> None:
        response = await client.post(RECEIPTS, json=receipt_body(items=[]))

        assert response.status_code == 422


class TestCurrency:
    async def test_a_yen_receipt_is_recorded_but_not_booked_yet(
        self, client: AsyncClient, ledger: FakeLedger
    ) -> None:
        yen = {
            "currency": "jpy",
            "total_sum": 1500,
            "items": [
                {"name": "Coffee", "expense_account": "Expenses:Groceries", "price": 500},
                {"name": "Onigiri", "expense_account": "Expenses:Groceries", "price": 1000},
            ],
        }
        created = await create_receipt(client, **yen)

        response = await client.post(
            f"{RECEIPTS}/{created['id']}/approve", json=receipt_body(**yen, payee="Lawson")
        )

        assert response.status_code == 400
        assert response.json()["message"].startswith(
            "Receipts in JPY cannot be booked to the ledger yet"
        )
        assert ledger.submitted == []
        fetched = (await client.get(f"{RECEIPTS}/{created['id']}")).json()
        assert (fetched["status"], fetched["payee"]) == ("unapproved", "Lawson")
        summary = (await client.get(RECEIPTS)).json()["items"][0]
        assert (summary["currency"], summary["total_sum"]) == ("JPY", 1500)

    async def test_receipts_default_to_euros(self, client: AsyncClient) -> None:
        body = receipt_body()
        del body["currency"]

        response = await client.post(RECEIPTS, json=body)

        assert response.json()["currency"] == "EUR"

    async def test_rejects_a_malformed_currency(self, client: AsyncClient) -> None:
        response = await client.post(RECEIPTS, json=receipt_body(currency="YEN1"))

        assert response.status_code == 422


class TestListReceipts:
    async def test_lists_newest_first_with_paging_and_item_counts(
        self, client: AsyncClient
    ) -> None:
        for payee in ["First", "Second", "Third"]:
            await create_receipt(client, payee=payee)

        page = (await client.get(RECEIPTS, params={"offset": 1, "limit": 1})).json()
        everything = (await client.get(RECEIPTS)).json()

        assert [r["payee"] for r in everything["items"]] == ["Third", "Second", "First"]
        assert everything["items"][0]["item_count"] == 3
        assert everything["items"][0]["has_ocr_issues"] is False
        assert (page["total"], page["offset"], page["limit"]) == (3, 1, 1)
        assert [r["payee"] for r in page["items"]] == ["Second"]

    async def test_filters_by_status(self, client: AsyncClient) -> None:
        approved = await create_receipt(client, payee="Approved")
        await create_receipt(client, payee="Pending")
        await client.post(f"{RECEIPTS}/{approved['id']}/approve", json=receipt_body())

        pending = (await client.get(RECEIPTS, params={"status": "unapproved"})).json()

        assert [r["payee"] for r in pending["items"]] == ["Pending"]
        assert pending["total"] == 1


class TestApproveReceipt:
    async def test_saves_edits_and_books_items_merged_by_account(
        self, client: AsyncClient, ledger: FakeLedger
    ) -> None:
        created = await create_receipt(client)
        milk, _bread, socks = created["items"]

        response = await client.post(
            f"{RECEIPTS}/{created['id']}/approve",
            json=receipt_body(
                payee="Prisma Kaleva",
                total_sum=13.0,
                items=[
                    {**milk, "price": 3.0},
                    {
                        "id": socks["id"],
                        "name": "Sukat",
                        "expense_account": "Expenses:Clothes",
                        "price": 7.0,
                    },
                    {"name": "Juusto", "expense_account": "Expenses:Groceries", "price": 3.0},
                ],
            ),
        )

        assert response.status_code == 200, response.text
        fetched = (await client.get(f"{RECEIPTS}/{created['id']}")).json()
        assert fetched["status"] == "approved"
        assert fetched["payee"] == "Prisma Kaleva"
        assert [(i["id"], i["name"]) for i in fetched["items"]] == [
            (milk["id"], "Maito"),
            (socks["id"], "Sukat"),
            (fetched["items"][2]["id"], "Juusto"),
        ]

        [transaction] = ledger.submitted
        assert transaction.receipt_id == created["id"]
        assert transaction.source_account == "Assets:Checking"
        assert transaction.total == 13.0
        assert [(p.expense_account, p.name, p.price) for p in transaction.postings] == [
            ("Expenses:Groceries", "Maito, Juusto", 6.0),
            ("Expenses:Clothes", "Sukat", 7.0),
        ]

    async def test_refuses_items_that_do_not_add_up_to_the_total(
        self, client: AsyncClient, ledger: FakeLedger
    ) -> None:
        created = await create_receipt(client)

        response = await client.post(
            f"{RECEIPTS}/{created['id']}/approve", json=receipt_body(total_sum=20.0)
        )

        assert response.status_code == 400
        assert response.json()["message"] == (
            "Items add up to 12.50 EUR, but the total is 20.00 EUR"
        )
        assert ledger.submitted == []
        fetched = (await client.get(f"{RECEIPTS}/{created['id']}")).json()
        assert (fetched["status"], fetched["total_sum"]) == ("unapproved", 20.0)

    async def test_needs_a_source_account(self, client: AsyncClient, ledger: FakeLedger) -> None:
        created = await create_receipt(client, source_account=None)

        response = await client.post(
            f"{RECEIPTS}/{created['id']}/approve", json=receipt_body(source_account="")
        )

        assert response.status_code == 400
        assert "paid from" in response.json()["message"]
        assert ledger.submitted == []

    async def test_an_approved_receipt_is_final(
        self, client: AsyncClient, ledger: FakeLedger
    ) -> None:
        created = await create_receipt(client)
        url = f"{RECEIPTS}/{created['id']}/approve"
        await client.post(url, json=receipt_body())

        again = await client.post(url, json=receipt_body(payee="Changed"))

        assert again.status_code == 400
        assert "already approved" in again.json()["message"]
        assert len(ledger.submitted) == 1
        assert (await client.get(f"{RECEIPTS}/{created['id']}")).json()["payee"] == "Prisma"

    async def test_ledger_rejection_keeps_the_receipt_unapproved_with_its_edits(
        self, client: AsyncClient, ledger: FakeLedger
    ) -> None:
        created = await create_receipt(client)
        ledger.reject_with = "Accounts not found: Assets:Checking"

        response = await client.post(
            f"{RECEIPTS}/{created['id']}/approve", json=receipt_body(payee="Edited")
        )

        assert response.status_code == 502
        assert response.json() == {
            "error": "bad_gateway",
            "message": "The ledger rejected the receipt: Accounts not found: Assets:Checking",
        }
        assert ledger.submitted == []
        fetched = (await client.get(f"{RECEIPTS}/{created['id']}")).json()
        assert (fetched["status"], fetched["booked"], fetched["payee"]) == (
            "unapproved",
            False,
            "Edited",
        )

    async def test_unavailable_ledger_is_reported(
        self, client: AsyncClient, ledger: FakeLedger
    ) -> None:
        created = await create_receipt(client)
        ledger.unavailable = True

        response = await client.post(f"{RECEIPTS}/{created['id']}/approve", json=receipt_body())

        assert response.status_code == 502
        assert "not available" in response.json()["message"]
        assert ledger.submitted == []
        fetched = (await client.get(f"{RECEIPTS}/{created['id']}")).json()
        assert (fetched["status"], fetched["booked"]) == ("unapproved", False)

    async def test_a_rejected_approval_can_be_retried_and_then_books(
        self, client: AsyncClient, ledger: FakeLedger
    ) -> None:
        created = await create_receipt(client)
        ledger.reject_with = "Accounts not found: Assets:Checking"
        await client.post(f"{RECEIPTS}/{created['id']}/approve", json=receipt_body())

        ledger.reject_with = None
        response = await client.post(f"{RECEIPTS}/{created['id']}/approve", json=receipt_body())

        assert response.status_code == 200, response.text
        assert (response.json()["status"], response.json()["booked"]) == ("approved", True)
        assert len(ledger.submitted) == 1

    async def test_unknown_receipt_is_not_found(self, client: AsyncClient) -> None:
        response = await client.post(f"{RECEIPTS}/999/approve", json=receipt_body())

        assert response.status_code == 404


class TestApproveRouting:
    """Approval routes by the source account's role and records `booked`."""

    async def test_personal_card_receipt_books_one_entry_and_ends_approved_and_booked(
        self, client: AsyncClient, ledger: FakeLedger, account_roles: FakeAccountRoles
    ) -> None:
        account_roles.roles = AccountRoles(personal_cards=("Assets:Checking",))
        created = await create_receipt(client)

        response = await client.post(f"{RECEIPTS}/{created['id']}/approve", json=receipt_body())

        assert response.status_code == 200, response.text
        assert (response.json()["status"], response.json()["booked"]) == ("approved", True)
        [transaction] = ledger.submitted
        assert transaction.source_account == "Assets:Checking"
        assert transaction.total == 12.5
        assert [(p.expense_account, p.name, p.price) for p in transaction.postings] == [
            ("Expenses:Groceries", "Maito, Leipä", 5.5),
            ("Expenses:Clothes", "Sukat", 7.0),
        ]
        detail = (await client.get(f"{RECEIPTS}/{created['id']}")).json()
        assert (detail["status"], detail["booked"]) == ("approved", True)
        row = (await client.get(RECEIPTS)).json()["items"][0]
        assert (row["status"], row["booked"]) == ("approved", True)

    async def test_shared_card_books_only_the_unshared_rows(
        self, client: AsyncClient, ledger: FakeLedger, account_roles: FakeAccountRoles
    ) -> None:
        account_roles.roles = SHARED_ROLES
        body = receipt_body(
            source_account="Liabilities:Shared",
            total_sum=12.0,
            items=[
                {"name": "Maito", "expense_account": "Expenses:Groceries", "price": 4.0},
                {
                    "name": "Pyyhe",
                    "expense_account": "Expenses:Household",
                    "price": 6.0,
                    "flatmate_share": 100,
                },
                {
                    "name": "Saippua",
                    "expense_account": "Expenses:Groceries",
                    "price": 2.0,
                    "flatmate_share": 50,
                },
            ],
        )
        created = await create_receipt(client, **body)

        response = await client.post(f"{RECEIPTS}/{created['id']}/approve", json=body)

        assert response.status_code == 200, response.text
        assert (response.json()["status"], response.json()["booked"]) == ("approved", True)
        [transaction] = ledger.submitted
        assert transaction.source_account == "Liabilities:Shared"
        assert transaction.total == 12.0
        assert [(p.expense_account, p.price) for p in transaction.postings] == [
            ("Expenses:Groceries", 4.0),
            ("Expenses:FlatmateAdjustment", -6.0),
            ("Liabilities:Shared", -4.0),
            ("Liabilities:Shared", 6.0),
        ]
        detail = (await client.get(f"{RECEIPTS}/{created['id']}")).json()
        assert (detail["status"], detail["booked"]) == ("approved", True)

    async def test_shared_card_receipt_with_only_shared_rows_is_approved_but_not_booked(
        self, client: AsyncClient, ledger: FakeLedger, account_roles: FakeAccountRoles
    ) -> None:
        account_roles.roles = SHARED_ROLES
        body = receipt_body(
            source_account="Liabilities:Shared",
            total_sum=6.0,
            items=[
                {
                    "name": "Saippua",
                    "expense_account": "Expenses:Groceries",
                    "price": 3.0,
                    "flatmate_share": 50,
                },
                {
                    "name": "Pyyhe",
                    "expense_account": "Expenses:Household",
                    "price": 3.0,
                    "flatmate_share": 25,
                },
            ],
        )
        created = await create_receipt(client, **body)

        response = await client.post(f"{RECEIPTS}/{created['id']}/approve", json=body)

        assert response.status_code == 200, response.text
        assert (response.json()["status"], response.json()["booked"]) == ("approved", False)
        assert ledger.submitted == []
        detail = (await client.get(f"{RECEIPTS}/{created['id']}")).json()
        assert (detail["status"], detail["booked"]) == ("approved", False)
        row = (await client.get(RECEIPTS)).json()["items"][0]
        assert (row["status"], row["booked"]) == ("approved", False)


class TestDeleteReceipt:
    async def test_deletes_receipt(self, client: AsyncClient) -> None:
        created = await create_receipt(client)

        response = await client.delete(f"{RECEIPTS}/{created['id']}")

        assert response.status_code == 204
        assert (await client.get(f"{RECEIPTS}/{created['id']}")).status_code == 404
        assert (await client.get(RECEIPTS)).json()["total"] == 0

    async def test_unknown_receipt_is_not_found(self, client: AsyncClient) -> None:
        assert (await client.delete(f"{RECEIPTS}/999")).status_code == 404
