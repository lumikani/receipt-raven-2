"""The local OCR output parser over the captured fixtures and small unit cases."""

import json
from datetime import date
from pathlib import Path

import pytest

from src.application.analysis.protocols.receipt_analyzer import ReceiptAnalysisError
from src.infrastructure.analysis.local_ocr.parser import parse_ocr_output

FIXTURES = Path(__file__).parents[2] / "fixtures" / "ocr"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def grounding_content(fixture_name: str) -> str:
    """The `choices[0].message.content` of a captured `/v1` response envelope."""
    envelope = json.loads(fixture(fixture_name))
    return str(envelope["choices"][0]["message"]["content"])


def test_herkkuduo_grounding_envelope_items_inline_in_a_text_block() -> None:
    result = parse_ocr_output(grounding_content("herkkuduo_grounding_response.json"), "local-model")

    assert result.payee == "Herkkuduo"
    assert result.receipt_date == date(2026, 5, 12)
    assert result.total == 11.76
    assert result.currency == "EUR"
    assert result.description is None
    assert result.model == "local-model"
    assert result.card_last_digits == "9841"
    assert [(p.name, p.price, p.expense_account) for p in result.products] == [
        ("Banaani 2 kpl 3,99 €", 7.98, ""),
        ("Maito 1 l 1,29 €", 1.29, ""),
        ("Leipä 400 g 2,49 €", 2.49, ""),
    ]


def test_s_market_grounding_output_items_from_an_html_table() -> None:
    result = parse_ocr_output(fixture("s-market_grounding_output.txt"), "local-model")

    assert result.payee == "S-Market"
    assert result.receipt_date == date(2026, 11, 1)  # ISO fallback
    assert result.total == 8.48
    assert result.card_last_digits is None
    assert [(p.name, p.price) for p in result.products] == [
        ("Omenamehu 1 l 2 kpl 2,50 €", 5.00),
        ("Kurkku 0,412 kg 2,39 €/kg", 0.99),
        ("Leipä 400 g 1 kpl", 2.49),
    ]


def test_prisma_plain_transcription_output() -> None:
    result = parse_ocr_output(fixture("prisma_transcription.txt"), "local-model")

    assert result.payee == "Prisma"  # first non-empty line, markdown heading stripped
    assert result.receipt_date == date(2026, 11, 3)
    assert result.total == 9.13
    assert result.card_last_digits == "1234"
    assert [(p.name, p.price, p.expense_account) for p in result.products] == [
        ("Kaurajuoma 1 l", 1.85, ""),
        ("Ruisleipä 400 g 1 kpl", 2.29, ""),
        ("Oliiviöljy 0,5 l", 4.99, ""),
    ]


def test_unit_rate_lines_and_rows_are_skipped() -> None:
    content = (
        "![title](0,0,100,50) Kauppa\n"
        "Kurkku 2,39 €/kg\n"
        "<table><tr><td>Banaani</td><td>1,20 €/KG</td></tr>"
        "<tr><td>Maito</td><td>1,29 €</td></tr></table>\n"
        "YHTEENSÄ 1,29 €\n"
    )

    result = parse_ocr_output(content, "m")

    assert [(p.name, p.price) for p in result.products] == [("Maito", 1.29)]


def test_currency_suffixed_integer_is_an_item_but_a_bare_integer_is_not() -> None:
    result = parse_ocr_output("Kauppa\nAleksanterinkatu 21\nKahvi 5 €\nYHTEENSÄ 5,00 €\n", "m")

    assert [(p.name, p.price) for p in result.products] == [("Kahvi", 5.00)]
    assert result.total == 5.00


def test_comma_decimals_and_unreadable_date() -> None:
    result = parse_ocr_output("Kauppa\n32.13.2026\nTuote 23,10 €\nYHTEENSÄ 23,10 €\n", "m")

    assert result.receipt_date is None
    assert result.total == 23.10
    assert result.products[0].price == 23.10


def test_missing_total_falls_back_to_the_item_sum() -> None:
    result = parse_ocr_output("Kauppa\nMaito 1,29 €\nLeipä 2,49 €\n", "m")

    assert result.total == 3.78


def test_card_digits_come_from_the_kortti_line() -> None:
    result = parse_ocr_output("Kauppa\nKortti: Visa Electron **** 4026\nMaito 1,29 €\n", "m")

    assert result.card_last_digits == "4026"


def test_empty_output_is_an_analysis_error() -> None:
    with pytest.raises(ReceiptAnalysisError):
        parse_ocr_output("  \n", "m")
