"""Unit tests for the balancing export: eligibility and exact-Decimal rows.

The export computation is a pure function over receipts (see
`src.domain.ledger.export`); these tests pin the eligibility matrix, the
formulas, the once-only half-up rounding and the description building.
"""

from datetime import date
from decimal import Decimal

from src.domain.ledger.account_roles import AccountRoles
from src.domain.ledger.export import build_export_rows, export_row, is_export_eligible
from src.domain.receipts.entities.receipt import Receipt, ReceiptLine

CARD = "liabilities:op:credit-card:gold"
SHARED = "liabilities:personal:shared-account"

ROLES = AccountRoles(
    personal_cards=(CARD,),
    shared_card=SHARED,
    flatmate_expense_adjustment="expenses:flatmate-expense-adjustment",
    purchase_for_flatmate="expenses:purchase-for-flatmate",
)
BOOKABLE = frozenset({"EUR"})


def line(
    name: str, price: float, share: float = 0.0, account: str = "expenses:food"
) -> ReceiptLine:
    return ReceiptLine(name, account, price, flatmate_share=share)


def receipt(
    *lines: ReceiptLine,
    source_account: str | None = CARD,
    currency: str = "EUR",
    approved: bool = True,
    payee: str = "K-Market",
    receipt_date: date = date(2026, 11, 2),
    description: str | None = None,
) -> Receipt:
    total = round(sum(item.price for item in lines), 2)
    subject = Receipt.create_manual(
        payee=payee,
        receipt_date=receipt_date,
        total_sum=total,
        lines=list(lines),
        description=description,
        source_account=source_account,
        currency=currency,
    )
    if approved:
        subject.approve(booked=True)
    return subject


class TestEligibility:
    def test_an_approved_personal_card_receipt_with_a_shared_item_is_eligible(self) -> None:
        subject = receipt(line("Maito", 4.0, share=50.0))

        assert is_export_eligible(subject, ROLES, BOOKABLE) is True

    def test_an_unapproved_receipt_is_not_eligible(self) -> None:
        subject = receipt(line("Maito", 4.0, share=50.0), approved=False)

        assert is_export_eligible(subject, ROLES, BOOKABLE) is False

    def test_a_shared_card_receipt_is_never_eligible(self) -> None:
        subject = receipt(line("Pyyhe", 6.0, share=100.0), source_account=SHARED)

        assert is_export_eligible(subject, ROLES, BOOKABLE) is False

    def test_a_receipt_in_a_non_bookable_currency_is_not_eligible(self) -> None:
        subject = receipt(line("Maito", 4.0, share=50.0), currency="JPY")

        assert is_export_eligible(subject, ROLES, BOOKABLE) is False

    def test_a_receipt_without_any_shared_item_is_not_eligible(self) -> None:
        subject = receipt(line("Maito", 4.0, share=0.0))

        assert is_export_eligible(subject, ROLES, BOOKABLE) is False

    def test_an_unconfigured_source_account_is_a_personal_card(self) -> None:
        subject = receipt(line("Maito", 4.0, share=100.0), source_account="Assets:Other")

        assert is_export_eligible(subject, ROLES, BOOKABLE) is True


class TestRowComputation:
    def test_shared_cost_is_two_times_share_over_100_times_price_of_partly_shared_items(
        self,
    ) -> None:
        subject = receipt(
            line("Maito", 4.0, share=50.0),  # 2 x 0.5 x 4.00 = 4.00
            line("Kahvi", 10.0, share=25.0),  # 2 x 0.25 x 10.00 = 5.00
            line("Leipä", 3.0, share=0.0),  # mine: not in shared_cost
            line("Pyyhe", 6.0, share=100.0),  # flatmate's: not in shared_cost
        )

        row = export_row(subject, ROLES, BOOKABLE)

        assert row is not None
        assert row.shared_cost == Decimal("9.00")
        assert row.purchase_for_flatmate == Decimal("6.00")

    def test_each_column_is_rounded_once_half_up_to_two_decimals(self) -> None:
        # 0.125 rounds half-up to 0.13 (banker's rounding would give 0.12);
        # two of them sum to exactly 0.25 before the single rounding.
        single = receipt(line("A", 0.25, share=25.0))
        double = receipt(line("A", 0.25, share=25.0), line("B", 0.25, share=25.0))

        single_row = export_row(single, ROLES, BOOKABLE)
        double_row = export_row(double, ROLES, BOOKABLE)
        assert single_row is not None
        assert double_row is not None
        assert single_row.shared_cost == Decimal("0.13")
        assert double_row.shared_cost == Decimal("0.25")

    def test_purchase_for_flatmate_sums_share_100_prices_rounded_once(self) -> None:
        subject = receipt(
            line("A", 0.10, share=100.0),
            line("B", 0.20, share=100.0),
            line("C", 0.125, share=100.0),
            line("Maito", 1.0, share=50.0),
        )

        row = export_row(subject, ROLES, BOOKABLE)

        assert row is not None
        assert row.purchase_for_flatmate == Decimal("0.43")  # 0.10 + 0.20 + 0.125 -> 0.425 -> 0.43
        assert row.shared_cost == Decimal("1.00")

    def test_amounts_stay_exact_decimals_not_floats(self) -> None:
        # 2 x (1/3 of 100) x 3.00 is not representable in binary floating point;
        # the exact decimal sum is 2.00, rounded once.
        subject = receipt(line("A", 3.0, share=100.0 / 3.0))

        row = export_row(subject, ROLES, BOOKABLE)

        assert row is not None
        assert isinstance(row.shared_cost, Decimal)
        assert row.shared_cost == Decimal("2.00")

    def test_description_is_mm_dd_payee_then_description_or_item_names(self) -> None:
        with_description = receipt(
            line("Maito", 4.0, share=50.0),
            payee="  K-Market  ",
            receipt_date=date(2026, 1, 5),
            description="Ruokaostokset",
        )
        without = receipt(
            line("Maito", 2.0, share=50.0),
            line("Kahvi", 2.0, share=100.0),
            receipt_date=date(2026, 12, 24),
        )

        described_row = export_row(with_description, ROLES, BOOKABLE)
        plain_row = export_row(without, ROLES, BOOKABLE)
        assert described_row is not None
        assert plain_row is not None
        assert described_row.description == "01-05 K-Market Ruokaostokset"
        assert plain_row.description == "12-24 K-Market Maito, Kahvi"


class TestBuildExportRows:
    def test_ineligible_receipts_are_dropped_and_the_order_is_kept(self) -> None:
        first = receipt(line("Maito", 4.0, share=50.0), receipt_date=date(2026, 10, 1))
        ineligible = receipt(line("Maito", 4.0, share=50.0), approved=False)
        shared_card = receipt(line("Pyyhe", 6.0, share=100.0), source_account=SHARED)
        last = receipt(line("Kahvi", 2.0, share=100.0), receipt_date=date(2026, 10, 3))

        rows = build_export_rows([first, ineligible, shared_card, last], ROLES, BOOKABLE)

        assert [row.description for row in rows] == [
            "10-01 K-Market Maito",
            "10-03 K-Market Kahvi",
        ]
