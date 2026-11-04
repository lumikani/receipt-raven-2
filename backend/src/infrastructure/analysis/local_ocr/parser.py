"""Turn local OCR model output into a `ReceiptAnalysis`.

The local model only supports two prompts — `""` (transcription to markdown)
and `"grounding"` (layout blocks of the form `![label](bbox) content`) — so
this parser accepts both shapes. Finnish receipt formats: comma decimals,
`dd.mm.yyyy` dates (ISO `yyyy-mm-dd` fallback) and the `YHTEENSÄ` total line.

Receipt items are read from HTML `table` blocks AND from item-looking text
lines (the model chooses the block type); unit-rate rows such as `2,39 €/KG`
are skipped. Every item gets an empty expense account: classification is the
rule engine's job, not the OCR model's.
"""

import html
import re
from datetime import date

from src.application.analysis.protocols.receipt_analyzer import (
    AnalysedProduct,
    ReceiptAnalysis,
    ReceiptAnalysisError,
)
from src.domain.receipts.entities.receipt import DEFAULT_CURRENCY

# `![label](x0,y0,x1,y1) content` — the grounding block marker.
GROUNDING_MARKER = re.compile(r"^!\[([A-Za-z+_]+)\]\([^)]*\)\s*")
TABLE_BLOCK = re.compile(r"<table[^>]*>(.*?)</table>", re.IGNORECASE | re.DOTALL)
TABLE_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
TABLE_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
HTML_TAG = re.compile(r"<[^>]+>")

# A whole-cell money amount, e.g. `7,98 €` or `23,10`.
MONEY = re.compile(r"^(\d+(?:[,.][0-9]{1,2})?)\s*(?:€|eur|EUR)?$")
# A text line whose trailing token is a money amount: `<name> <amount> <€?>`.
# The amount must carry decimals or a currency marker, so address-like lines
# (`Aleksanterinkatu 21`) are not mistaken for items.
MONEY_AT_END = re.compile(
    r"^(?P<name>.+?)\s+(?P<amount>\d+(?:[,.])\d{1,2}|\d+)\s*(?P<currency>€|eur|EUR)?$"
)
# Unit-rate rows carry a per-unit price instead of a total: `2,39 €/KG`.
UNIT_RATE_AT_END = re.compile(r"\d+(?:[,.])\d{1,2}\s*€\s*/\s*[A-Za-z]+\s*$")
UNIT_RATE_CELL = re.compile(r"^\d+(?:[,.])\d{1,2}\s*€\s*/\s*[A-Za-z]+$")
# Any money token inside a line, not glued to date-like or unit-rate numbers.
MONEY_TOKEN = re.compile(r"(?<![\d.,])(\d+(?:[,.])\d{1,2})(?![\d.,/])")

# A table row needs a name cell and a price cell; card digits are 4 long.
MIN_ROW_CELLS = 2
CARD_DIGITS = 4

DATE_DMY = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
DATE_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
CARD_LINE = re.compile(r"kortti", re.IGNORECASE)
TOTAL_LINE = re.compile(r"yhteensä", re.IGNORECASE)
DIGIT_RUN = re.compile(r"\d+")
HEADING = re.compile(r"^#+\s*")


def _strip_marker(line: str) -> tuple[str | None, str]:
    """Split a grounding marker off a line: `(label, rest)`. Label None if plain."""
    match = GROUNDING_MARKER.match(line)
    if match:
        return match.group(1).lower(), line[match.end() :]
    return None, line


def _clean(text: str) -> str:
    """Strip HTML tags, unescape entities and collapse whitespace."""
    return re.sub(r"\s+", " ", html.unescape(HTML_TAG.sub(" ", text))).strip()


def _parse_money(text: str) -> float | None:
    """Parse a whole-cell amount such as `7,98 €`; None when not plain money."""
    match = MONEY.match(text.strip())
    if not match:
        return None
    return round(float(match.group(1).replace(",", ".")), 2)


def _parse_date_in(line: str) -> date | None:
    """The first valid `dd.mm.yyyy` date in the line, else an ISO `yyyy-mm-dd`."""
    for groups in DATE_DMY.findall(line):
        try:
            return date(int(groups[2]), int(groups[1]), int(groups[0]))
        except ValueError:
            continue
    for groups in DATE_ISO.findall(line):
        try:
            return date(int(groups[0]), int(groups[1]), int(groups[2]))
        except ValueError:
            continue
    return None


def _table_items(content: str) -> list[AnalysedProduct]:
    """Items from HTML table rows whose last cell is a plain money amount."""
    items: list[AnalysedProduct] = []
    for block in TABLE_BLOCK.findall(content):
        for row in TABLE_ROW.findall(block):
            cells = [_clean(cell) for cell in TABLE_CELL.findall(row)]
            cells = [cell for cell in cells if cell]
            if len(cells) < MIN_ROW_CELLS:
                continue
            price_cell = cells[-1]
            if UNIT_RATE_CELL.match(price_cell):
                continue  # a per-unit rate row, not a purchased item
            price = _parse_money(price_cell)
            if price is None:
                continue
            name = " ".join(cells[:-1])
            items.append(AnalysedProduct(name=name, expense_account="", price=price))
    return items


def _text_items(text: str) -> list[AnalysedProduct]:
    """Items from item-looking text lines: `<name> <amount> <€?>`, trailing price."""
    items: list[AnalysedProduct] = []
    for raw_line in text.splitlines():
        _, line = _strip_marker(raw_line)
        line = line.strip()
        if not line or TOTAL_LINE.search(line) or CARD_LINE.search(line):
            continue
        if UNIT_RATE_AT_END.search(line):
            continue
        match = MONEY_AT_END.match(line)
        if not match:
            continue
        amount = match.group("amount")
        if not match.group("currency") and not re.search(r"[,.]", amount):
            continue  # a bare integer is not a price (e.g. a street number)
        name = re.sub(r"\s+", " ", match.group("name")).strip()
        if not name:
            continue
        items.append(
            AnalysedProduct(
                name=name,
                expense_account="",
                price=round(float(match.group("amount").replace(",", ".")), 2),
            )
        )
    return items


def _total(text: str, items: list[AnalysedProduct]) -> float:
    """The `YHTEENSÄ` line's amount; falls back to the sum of the items."""
    for raw_line in text.splitlines():
        _, line = _strip_marker(raw_line)
        if TOTAL_LINE.search(line):
            tokens = MONEY_TOKEN.findall(line)
            if tokens:
                return round(float(tokens[-1].replace(",", ".")), 2)
    return round(sum(item.price for item in items), 2)


def _payee(lines: list[tuple[str | None, str]]) -> str:
    """First line of the `title` block, else the first non-empty line."""
    for label, line in lines:
        if label == "title" and line.strip():
            return HEADING.sub("", line.strip())
    for _, line in lines:
        if line.strip():
            return HEADING.sub("", line.strip())
    return ""


def _card_last_digits(text: str) -> str | None:
    """Last 4 digits from a card line, e.g. `Kortti: MasterCard **** **** 9841`."""
    digits: str | None = None
    for raw_line in text.splitlines():
        if not CARD_LINE.search(raw_line):
            continue
        runs = [run for run in DIGIT_RUN.findall(raw_line) if len(run) >= CARD_DIGITS]
        if runs:
            digits = runs[-1][-CARD_DIGITS:]
    return digits


def parse_ocr_output(content: str, model: str) -> ReceiptAnalysis:
    """Parse grounding blocks or plain transcription into a `ReceiptAnalysis`.

    Raises:
        ReceiptAnalysisError: If the output is empty.
    """
    if not content.strip():
        raise ReceiptAnalysisError("The OCR model returned an empty receipt text")
    lines = [_strip_marker(raw) for raw in content.splitlines()]
    lines = [(label, line.strip()) for label, line in lines]
    text_without_tables = TABLE_BLOCK.sub(" ", content)

    items = _table_items(content) + _text_items(text_without_tables)
    receipt_date: date | None = None
    for _, line in lines:
        receipt_date = _parse_date_in(line)
        if receipt_date is not None:
            break

    return ReceiptAnalysis(
        payee=_payee(lines),
        description=None,
        receipt_date=receipt_date,
        products=tuple(items),
        total=_total(text_without_tables, items),
        model=model,
        currency=DEFAULT_CURRENCY,
        card_last_digits=_card_last_digits(content),
    )
