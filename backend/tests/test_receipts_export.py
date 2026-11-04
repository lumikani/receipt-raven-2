"""API tests for GET /api/v1/receipts/export.csv: the balancing export.

One row per eligible approved personal-card receipt, as a `;`-delimited
comma-decimal CSV download and a headerless TSV "Copy for Sheets" variant.
"""

from typing import Any

from httpx import AsyncClient

from src.domain.ledger.account_roles import AccountRoles
from tests.fakes import FakeAccountRoles

RECEIPTS = "/api/v1/receipts"
EXPORT = f"{RECEIPTS}/export.csv"

HEADER = "shared_cost;description;purchase_for_flatmate\r\n"

SHARED_ROLES = AccountRoles(
    personal_cards=("Assets:Checking",),
    shared_card="Liabilities:Shared",
    flatmate_expense_adjustment="Expenses:FlatmateAdjustment",
    purchase_for_flatmate="Expenses:PurchaseForFlatmate",
)


def body(**overrides: object) -> dict[str, Any]:
    """A receipt body with one 50%-shared item and one flatmate-only item."""
    base: dict[str, Any] = {
        "payee": "Prisma",
        "description": None,
        "source_account": "Assets:Checking",
        "date": "2026-10-01",
        "total_sum": 10.0,
        "currency": "EUR",
        "items": [
            {
                "name": "Maito",
                "expense_account": "Expenses:Groceries",
                "price": 4.0,
                "flatmate_share": 50,
            },
            {
                "name": "Pyyhe",
                "expense_account": "Expenses:Household",
                "price": 6.0,
                "flatmate_share": 100,
            },
        ],
    }
    base.update(overrides)
    return base


async def create_receipt(client: AsyncClient, **overrides: object) -> dict[str, Any]:
    response = await client.post(RECEIPTS, json=body(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


async def create_and_approve(client: AsyncClient, **overrides: object) -> dict[str, Any]:
    payload = body(**overrides)
    created = await create_receipt(client, **overrides)
    response = await client.post(f"{RECEIPTS}/{created['id']}/approve", json=payload)
    assert response.status_code == 200, response.text
    return created


def default_row(payee: str = "Prisma", date: str = "2026-10-01") -> str:
    """The row of the default body: shared 4,00, purchase 6,00."""
    return f"4,00;{date[5:]} {payee} Maito, Pyyhe;6,00\r\n"


class TestExportResponse:
    async def test_download_headers_and_header_only_body_when_nothing_is_eligible(
        self, client: AsyncClient
    ) -> None:
        response = await client.get(EXPORT)

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert (
            response.headers["content-disposition"] == 'attachment; filename="receipts-export.csv"'
        )
        assert response.text == HEADER

    async def test_the_route_is_not_swallowed_by_the_receipt_id_path(
        self, client: AsyncClient
    ) -> None:
        # GET /receipts/{receipt_id} would fail to parse "export.csv" as an int.
        assert (await client.get(EXPORT)).status_code == 200
        assert (await client.get(f"{RECEIPTS}/export.csv", params={"ids": "999"})).text == HEADER

    async def test_tsv_variant_is_headerless_tab_separated_with_comma_decimals(
        self, client: AsyncClient
    ) -> None:
        await create_and_approve(client)

        response = await client.get(EXPORT, params={"format": "tsv"})

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/tab-separated-values; charset=utf-8"
        assert response.text == "4,00\t10-01 Prisma Maito, Pyyhe\t6,00\r\n"

    async def test_tsv_variant_of_an_empty_selection_is_empty(self, client: AsyncClient) -> None:
        response = await client.get(EXPORT, params={"format": "tsv"})

        assert response.status_code == 200
        assert response.text == ""

    async def test_malformed_selection_parameters_are_rejected(self, client: AsyncClient) -> None:
        assert (await client.get(EXPORT, params={"ids": "1,abc"})).status_code == 422
        assert (await client.get(EXPORT, params={"format": "xml"})).status_code == 422
        assert (await client.get(EXPORT, params={"from": "2026-13-40"})).status_code == 422


class TestSelection:
    async def test_no_params_exports_every_eligible_receipt_ordered_by_date_then_id(
        self, client: AsyncClient
    ) -> None:
        await create_and_approve(client, payee="Third", date="2026-10-03")
        await create_and_approve(client, payee="First", date="2026-10-01")
        await create_and_approve(client, payee="Second", date="2026-10-02")
        # Same date as "Second": the higher id sorts after it.
        await create_and_approve(client, payee="SecondToo", date="2026-10-02")

        response = await client.get(EXPORT)

        assert response.text == (
            HEADER
            + "4,00;10-01 First Maito, Pyyhe;6,00\r\n"
            + "4,00;10-02 Second Maito, Pyyhe;6,00\r\n"
            + "4,00;10-02 SecondToo Maito, Pyyhe;6,00\r\n"
            + "4,00;10-03 Third Maito, Pyyhe;6,00\r\n"
        )

    async def test_ids_selects_only_those_receipts(self, client: AsyncClient) -> None:
        one = await create_and_approve(client, payee="One", date="2026-10-01")
        await create_and_approve(client, payee="Two", date="2026-10-02")
        three = await create_and_approve(client, payee="Three", date="2026-10-03")

        response = await client.get(EXPORT, params={"ids": f"{one['id']},{three['id']}"})

        assert response.text == (
            HEADER
            + "4,00;10-01 One Maito, Pyyhe;6,00\r\n"
            + "4,00;10-03 Three Maito, Pyyhe;6,00\r\n"
        )

    async def test_ids_of_ineligible_receipts_still_export_nothing_for_them(
        self, client: AsyncClient
    ) -> None:
        eligible = await create_and_approve(client, payee="Eligible")
        pending = await create_receipt(client, payee="Pending")

        response = await client.get(EXPORT, params={"ids": f"{eligible['id']},{pending['id']}"})

        assert response.text == HEADER + default_row("Eligible")

    async def test_from_and_to_are_inclusive(self, client: AsyncClient) -> None:
        await create_and_approve(client, payee="Before", date="2026-10-01")
        await create_and_approve(client, payee="In", date="2026-10-02")
        await create_and_approve(client, payee="After", date="2026-10-03")

        response = await client.get(EXPORT, params={"from": "2026-10-02", "to": "2026-10-02"})
        assert response.text == HEADER + "4,00;10-02 In Maito, Pyyhe;6,00\r\n"

        response = await client.get(EXPORT, params={"from": "2026-10-02"})
        assert [line.split(";")[1] for line in response.text.splitlines()[1:]] == [
            "10-02 In Maito, Pyyhe",
            "10-03 After Maito, Pyyhe",
        ]

        response = await client.get(EXPORT, params={"to": "2026-10-02"})
        assert [line.split(";")[1] for line in response.text.splitlines()[1:]] == [
            "10-01 Before Maito, Pyyhe",
            "10-02 In Maito, Pyyhe",
        ]

    async def test_ids_and_date_range_combine(self, client: AsyncClient) -> None:
        in_range = await create_and_approve(client, payee="In", date="2026-10-02")
        out_of_range = await create_and_approve(client, payee="Out", date="2026-10-03")

        response = await client.get(
            EXPORT, params={"ids": f"{in_range['id']},{out_of_range['id']}", "to": "2026-10-02"}
        )

        assert response.text == HEADER + "4,00;10-02 In Maito, Pyyhe;6,00\r\n"


class TestEligibility:
    async def test_only_approved_personal_card_receipts_with_a_shared_item_are_exported(
        self, client: AsyncClient, account_roles: FakeAccountRoles
    ) -> None:
        account_roles.roles = SHARED_ROLES
        await create_receipt(client, payee="Unapproved")  # would be eligible if approved
        await create_and_approve(
            client,
            payee="NoShare",
            items=[{"name": "Maito", "expense_account": "Expenses:Groceries", "price": 10.0}],
        )
        await create_and_approve(
            client,
            payee="SharedCard",
            source_account="Liabilities:Shared",
            items=[
                {
                    "name": "Saippua",
                    "expense_account": "Expenses:Groceries",
                    "price": 10.0,
                    "flatmate_share": 50,
                }
            ],
        )
        await create_and_approve(client, payee="Eligible")

        response = await client.get(EXPORT)

        assert response.text == HEADER + default_row("Eligible")

    async def test_an_unconfigured_source_account_defaults_to_the_personal_card_role(
        self, client: AsyncClient
    ) -> None:
        # The default FakeAccountRoles is empty, so "Assets:Checking" is unconfigured.
        await create_and_approve(client, payee="DefaultRole")

        assert (await client.get(EXPORT)).text == HEADER + default_row("DefaultRole")

    async def test_a_shared_card_receipt_is_never_eligible(
        self, client: AsyncClient, account_roles: FakeAccountRoles
    ) -> None:
        account_roles.roles = SHARED_ROLES
        await create_and_approve(
            client,
            source_account="Liabilities:Shared",
            items=[
                {
                    "name": "Pyyhe",
                    "expense_account": "Expenses:Household",
                    "price": 10.0,
                    "flatmate_share": 100,
                }
            ],
        )

        assert (await client.get(EXPORT)).text == HEADER


class TestRowComputation:
    async def test_shared_cost_is_exact_decimal_rounded_once_half_up(
        self, client: AsyncClient
    ) -> None:
        # Each item contributes 2 x (25/100) x 0.25 = 0.125 exactly; rounded
        # per item half-up that would be 0.13 + 0.13, rounded once it is 0.25.
        await create_and_approve(
            client,
            payee="RoundOnce",
            total_sum=0.50,
            items=[
                {
                    "name": "A",
                    "expense_account": "Expenses:Groceries",
                    "price": 0.25,
                    "flatmate_share": 25,
                },
                {
                    "name": "B",
                    "expense_account": "Expenses:Groceries",
                    "price": 0.25,
                    "flatmate_share": 25,
                },
            ],
        )
        # A single 0.125 rounds half-up to 0.13 (banker's rounding would give 0.12).
        await create_and_approve(
            client,
            payee="HalfUp",
            date="2026-10-02",
            total_sum=0.25,
            items=[
                {
                    "name": "C",
                    "expense_account": "Expenses:Groceries",
                    "price": 0.25,
                    "flatmate_share": 25,
                },
            ],
        )

        response = await client.get(EXPORT)

        assert response.text == (
            HEADER + "0,25;10-01 RoundOnce A, B;0,00\r\n" + "0,13;10-02 HalfUp C;0,00\r\n"
        )

    async def test_purchase_for_flatmate_sums_the_share_100_prices(
        self, client: AsyncClient
    ) -> None:
        await create_and_approve(
            client,
            total_sum=0.80,
            items=[
                {"name": "Maito", "expense_account": "Expenses:Groceries", "price": 0.50},
                {
                    "name": "Pyyhe",
                    "expense_account": "Expenses:Household",
                    "price": 0.10,
                    "flatmate_share": 100,
                },
                {
                    "name": "Saippua",
                    "expense_account": "Expenses:Household",
                    "price": 0.20,
                    "flatmate_share": 100,
                },
            ],
        )

        response = await client.get(EXPORT)

        # The share-0 item contributes nowhere; the two share-100 items sum to 0,30.
        assert response.text == HEADER + "0,00;10-01 Prisma Maito, Pyyhe, Saippua;0,30\r\n"

    async def test_description_is_mm_dd_payee_then_description_or_item_names(
        self, client: AsyncClient
    ) -> None:
        await create_and_approve(
            client, payee="  K-Market  ", description="Ruokaostokset", date="2026-11-05"
        )
        await create_and_approve(client, payee="Prisma", date="2026-11-06")

        response = await client.get(EXPORT)

        assert response.text == (
            HEADER
            + "4,00;11-05 K-Market Ruokaostokset;6,00\r\n"
            + "4,00;11-06 Prisma Maito, Pyyhe;6,00\r\n"
        )

    async def test_csv_quotes_fields_containing_delimiter_quote_or_newline(
        self, client: AsyncClient
    ) -> None:
        await create_and_approve(client, description='Kahvi; "x"\nleipä')

        response = await client.get(EXPORT)

        assert response.text == (HEADER + '4,00;"10-01 Prisma Kahvi; ""x""\nleipä";6,00\r\n')
