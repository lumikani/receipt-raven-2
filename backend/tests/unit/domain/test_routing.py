"""Unit tests for build_routed_transaction: the pure ledger-routing function.

Routing depends on the source account's configured role and each item's
flatmate share only — never on other classification inputs.
"""

from datetime import date

from src.domain.ledger.account_roles import AccountRoles
from src.domain.ledger.receipt_transaction import ReceiptPosting
from src.domain.ledger.routing import build_routed_transaction
from src.domain.receipts.entities.receipt import Receipt, ReceiptLine

CARD = "liabilities:op:credit-card:gold"
SHARED = "liabilities:personal:shared-account"
ADJUSTMENT = "expenses:flatmate-expense-adjustment"
PURCHASE_FOR_FLATMATE = "expenses:purchase-for-flatmate"

ROLES = AccountRoles(
    personal_cards=(CARD,),
    shared_card=SHARED,
    flatmate_expense_adjustment=ADJUSTMENT,
    purchase_for_flatmate=PURCHASE_FOR_FLATMATE,
)


def receipt(source_account: str | None, *lines: ReceiptLine) -> Receipt:
    total = round(sum(line.price for line in lines), 2)
    return Receipt.create_manual(
        payee="K-Market",
        receipt_date=date(2026, 11, 2),
        total_sum=total,
        lines=list(lines),
        source_account=source_account,
    )


def line(name: str, account: str, price: float, share: float = 0.0) -> ReceiptLine:
    return ReceiptLine(name, account, price, flatmate_share=share)


# Personal card


def test_personal_card_books_one_entry_with_all_rows_positive_and_merged_per_account() -> None:
    subject = receipt(
        CARD,
        line("Kahvi", "expenses:food", 10.0),
        line("Maito", "expenses:food", 5.0, share=50.0),
        line("Kynä", "expenses:office", 2.0),
    )

    tx = build_routed_transaction(subject, ROLES)

    assert tx is not None
    assert tx.receipt_id == subject.id.value
    assert tx.payee == "K-Market"
    assert tx.receipt_date == date(2026, 11, 2)
    assert tx.source_account == CARD
    # The total is the receipt total; the renderer adds the -sum balancing leg.
    assert tx.total == 17.0
    assert tx.currency == "EUR"
    assert tx.postings == (
        ReceiptPosting("Kahvi, Maito", "expenses:food", 15.0),
        ReceiptPosting("Kynä", "expenses:office", 2.0),
    )
    assert round(sum(p.price for p in tx.postings), 2) == tx.total


def test_personal_card_remaps_share_100_rows_to_the_purchase_for_flatmate_account() -> None:
    subject = receipt(
        CARD,
        line("Kahvi", "expenses:food", 10.0),
        line("Zucchini", "expenses:food", 15.0, share=100.0),
        line("Kurkku", "expenses:food", 4.0, share=100.0),
    )

    tx = build_routed_transaction(subject, ROLES)

    assert tx is not None
    assert tx.postings == (
        ReceiptPosting("Kahvi", "expenses:food", 10.0),
        ReceiptPosting("Zucchini, Kurkku", PURCHASE_FOR_FLATMATE, 19.0),
    )


def test_unconfigured_source_account_is_routed_as_a_personal_card() -> None:
    subject = receipt(
        "Assets:Checking",
        line("Kahvi", "expenses:food", 10.0, share=100.0),
    )

    tx = build_routed_transaction(subject, ROLES)

    assert tx is not None
    assert tx.source_account == "Assets:Checking"
    assert tx.postings == (ReceiptPosting("Kahvi", PURCHASE_FOR_FLATMATE, 10.0),)


def test_empty_roles_route_as_personal_and_keep_share_100_rows_on_their_account() -> None:
    subject = receipt(
        SHARED,  # even the shared-card name is just a personal card without config
        line("Zucchini", "expenses:food", 15.0, share=100.0),
    )

    tx = build_routed_transaction(subject, AccountRoles())

    assert tx is not None
    assert tx.source_account == SHARED
    assert tx.postings == (ReceiptPosting("Zucchini", "expenses:food", 15.0),)
    assert tx.total == 15.0


# Shared card


def test_shared_card_routes_mine_and_flatmates_rows_with_zero_summing_legs() -> None:
    subject = receipt(
        SHARED,
        line("Kahvi", "expenses:food", 10.0, share=0.0),
        line("Zucchini", "expenses:food", 15.0, share=100.0),
        line("Maito", "expenses:food", 5.0, share=50.0),  # shared: routed nowhere
    )

    tx = build_routed_transaction(subject, ROLES)

    assert tx is not None
    assert tx.source_account == SHARED
    assert tx.postings == (
        ReceiptPosting("Kahvi", "expenses:food", 10.0),
        ReceiptPosting("Zucchini", ADJUSTMENT, -15.0),
        # Separate, unmerged liability legs: -10 credit (I owe the shared
        # account), +15 debit (the shared account owes me) -> net +5.
        ReceiptPosting("Kahvi", SHARED, -10.0),
        ReceiptPosting("Zucchini", SHARED, 15.0),
    )
    assert round(sum(p.price for p in tx.postings), 2) == 0.0
    # The worked example: -10 + 15 -> net +5 "the shared account owes me".
    liability_net = sum(p.price for p in tx.postings if p.expense_account == SHARED)
    assert round(liability_net, 2) == 5.0


def test_shared_card_merges_share_0_rows_per_expense_account() -> None:
    subject = receipt(
        SHARED,
        line("Kahvi", "expenses:food", 6.0),
        line("Maito", "expenses:food", 4.0),
        line("Kynä", "expenses:office", 2.0),
    )

    tx = build_routed_transaction(subject, ROLES)

    assert tx is not None
    assert tx.postings == (
        ReceiptPosting("Kahvi, Maito", "expenses:food", 10.0),
        ReceiptPosting("Kynä", "expenses:office", 2.0),
        ReceiptPosting("Kahvi, Maito, Kynä", SHARED, -12.0),
    )
    assert round(sum(p.price for p in tx.postings), 2) == 0.0


def test_shared_card_with_only_share_0_rows_books_expenses_plus_a_credit() -> None:
    subject = receipt(SHARED, line("Kahvi", "expenses:food", 10.0, share=0.0))

    tx = build_routed_transaction(subject, ROLES)

    assert tx is not None
    assert tx.postings == (
        ReceiptPosting("Kahvi", "expenses:food", 10.0),
        ReceiptPosting("Kahvi", SHARED, -10.0),
    )


def test_shared_card_with_only_share_100_rows_books_the_adjustment_plus_a_debit() -> None:
    subject = receipt(SHARED, line("Zucchini", "expenses:food", 15.0, share=100.0))

    tx = build_routed_transaction(subject, ROLES)

    assert tx is not None
    assert tx.postings == (
        ReceiptPosting("Zucchini", ADJUSTMENT, -15.0),
        ReceiptPosting("Zucchini", SHARED, 15.0),
    )
    assert round(sum(p.price for p in tx.postings), 2) == 0.0


def test_shared_card_with_only_shared_rows_is_approved_without_a_ledger_entry() -> None:
    subject = receipt(
        SHARED,
        line("Kahvi", "expenses:food", 10.0, share=50.0),
        line("Maito", "expenses:food", 5.0, share=25.0),
    )

    assert build_routed_transaction(subject, ROLES) is None
