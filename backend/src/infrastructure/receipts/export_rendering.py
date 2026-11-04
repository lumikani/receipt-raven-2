"""Render balancing-export rows as a downloadable CSV or a clipboard TSV.

The CSV download is `;`-delimited with comma decimal separators and always a
header row, RFC 4180 quoting (fields containing the delimiter, a quote or a
newline) and CRLF lines. The TSV "Copy for Sheets" variant carries the same
rows tab-separated with no header, so pasting into a spreadsheet splits on
tabs and parses the comma decimals as numbers.
"""

import csv
import io
from collections.abc import Sequence
from decimal import Decimal

from src.domain.ledger.export import BalancingExportRow

EXPORT_HEADER = ("shared_cost", "description", "purchase_for_flatmate")


def render_csv(rows: Sequence[BalancingExportRow]) -> str:
    """`;`-delimited comma-decimal CSV with a header row (header-only when empty)."""
    return _render(rows, delimiter=";", header=True)


def render_tsv(rows: Sequence[BalancingExportRow]) -> str:
    """Tab-separated comma-decimal TSV without a header row."""
    return _render(rows, delimiter="\t", header=False)


def _render(rows: Sequence[BalancingExportRow], *, delimiter: str, header: bool) -> str:
    buffer = io.StringIO()
    # csv's defaults are RFC 4180: QUOTE_MINIMAL quoting and CRLF line endings.
    writer = csv.writer(buffer, delimiter=delimiter)
    if header:
        writer.writerow(EXPORT_HEADER)
    for row in rows:
        writer.writerow(
            [
                _comma_decimal(row.shared_cost),
                row.description,
                _comma_decimal(row.purchase_for_flatmate),
            ]
        )
    return buffer.getvalue()


def _comma_decimal(value: Decimal) -> str:
    """A two-decimal amount with a comma decimal separator, e.g. `12,50`."""
    return format(value, "f").replace(".", ",")
