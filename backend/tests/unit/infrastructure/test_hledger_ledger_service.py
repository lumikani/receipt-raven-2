"""The hledger ledger adapter against a scripted command runner.

The runner seam fakes the CLI: unit tests assert the argv shapes, the rendered
journal text, the validation flow and the rc/stderr error mapping (the stderr
strings are real hledger 1.32.3 output). One integration test runs the real
binary against a temp journal and is skipped when no `hledger` is on PATH.
"""

import asyncio
import shutil
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from src.config import Settings
from src.domain.ledger.account import AccountType, LedgerAccount
from src.domain.ledger.exceptions import LedgerRejectedTransactionError, LedgerUnavailableError
from src.domain.ledger.receipt_transaction import ReceiptPosting, ReceiptTransaction
from src.infrastructure.ledger.beancount_ledger_service import BeancountLedgerService
from src.infrastructure.ledger.hledger_ledger_service import (
    CommandResult,
    CommandRunner,
    HledgerLedgerService,
    render_entry,
    run_hledger_command,
)
from src.infrastructure.ledger.ledger_service_factory import build_ledger_service

TRANSACTION = ReceiptTransaction(
    receipt_id=42,
    payee="Prisma",
    description="weekly shop",
    receipt_date=date(2026, 10, 9),
    source_account="liabilities:card",
    total=15.79,
    currency="EUR",
    postings=(
        ReceiptPosting("Banaani, Maito", "expenses:groceries", 4.28),
        ReceiptPosting("T-paita", "expenses:clothes", 11.51),
    ),
)

# Real hledger 1.32.3 stderr for an unbalanced transaction.
UNBALANCED_STDERR = (
    "hledger: Error: /tmp/receipts.journal.validate:2-4:\n"
    "2 | 2026-10-09 * Prisma | weekly shop\n"
    "  |     expenses:groceries       4.28 EUR\n"
    "\n"
    "This transaction is unbalanced.\n"
)

RunnerHandler = Callable[[list[str]], Awaitable[CommandResult]]


def fake_runner(handler: RunnerHandler) -> tuple[CommandRunner, list[list[str]]]:
    calls: list[list[str]] = []

    async def run(argv: Sequence[str]) -> CommandResult:
        calls.append(list(argv))
        return await handler(list(argv))

    return run, calls


def sync(result: CommandResult) -> RunnerHandler:
    async def handler(argv: list[str]) -> CommandResult:
        return result

    return handler


def service(
    tmp_path: Path, handler: RunnerHandler, binary: str = "hledger"
) -> tuple[HledgerLedgerService, list[list[str]]]:
    runner, calls = fake_runner(handler)
    return HledgerLedgerService(
        read_file=tmp_path / "main.journal",
        append_file=tmp_path / "receipts.journal",
        binary=binary,
        timeout_seconds=10,
        command_runner=runner,
    ), calls


# --- Entry rendering --------------------------------------------------------


def test_render_entry_formats_header_postings_and_balancing_leg() -> None:
    assert render_entry(TRANSACTION) == (
        "2026-10-09 * Prisma | weekly shop\n"
        "    expenses:groceries  4.28 EUR  ; items: Banaani, Maito\n"
        "    expenses:clothes  11.51 EUR  ; items: T-paita\n"
        "    liabilities:card  -15.79 EUR\n"
        "    ; receipt-id: 42\n"
    )


def test_render_entry_omits_the_description_separator_when_unset() -> None:
    entry = render_entry(replace(TRANSACTION, description=None))

    assert entry.splitlines()[0] == "2026-10-09 * Prisma"


def test_render_entry_adds_no_balancing_leg_when_postings_sum_to_zero() -> None:
    transaction = replace(
        TRANSACTION,
        postings=(
            ReceiptPosting("x", "expenses:a", 10.00),
            ReceiptPosting("y", "liabilities:shared", -10.00),
        ),
    )

    entry = render_entry(transaction)

    assert "liabilities:card" not in entry
    assert entry.endswith("    ; receipt-id: 42\n")


# --- Reads ------------------------------------------------------------------


async def test_lists_accounts_from_the_read_journal_by_type(tmp_path: Path) -> None:
    stdout = (
        "assets:checking       ; type: C\n"
        "expenses:groceries    ; type: X\n"
        "liabilities:card      ; type: L\n"
        "income:salary         ; type: R\n"
        "equity:opening        ; type: E\n"
        "weird:thing           ; type: Z\n"
    )
    subject, calls = service(tmp_path, sync(CommandResult(0, stdout, "")))

    assert await subject.list_accounts() == [
        LedgerAccount("assets:checking", AccountType.ASSETS),
        LedgerAccount("expenses:groceries", AccountType.EXPENSES),
        LedgerAccount("liabilities:card", AccountType.LIABILITIES),
        LedgerAccount("income:salary", AccountType.INCOME),
        LedgerAccount("equity:opening", AccountType.EQUITY),
    ]
    assert calls == [
        ["hledger", "-f", str(tmp_path / "main.journal"), "accounts", "--used", "--types"]
    ]

    assert await subject.list_accounts(AccountType.EXPENSES) == [
        LedgerAccount("expenses:groceries", AccountType.EXPENSES)
    ]


async def test_lists_payees_from_the_read_journal(tmp_path: Path) -> None:
    subject, calls = service(tmp_path, sync(CommandResult(0, "K-Market\nPrisma\n\n", "")))

    assert await subject.list_payees() == ["K-Market", "Prisma"]
    assert calls == [["hledger", "-f", str(tmp_path / "main.journal"), "payees"]]


# --- Submit: validate then append -------------------------------------------


async def test_submit_validates_a_temp_copy_then_appends(tmp_path: Path) -> None:
    append = tmp_path / "receipts.journal"
    existing = (
        "2026-01-01 * K-Market\n"
        "    expenses:groceries  10.00 EUR\n"
        "    liabilities:card  -10.00 EUR\n"
    )
    append.write_text(existing, encoding="utf-8")
    validated: list[str] = []

    async def ok_bal(argv: list[str]) -> CommandResult:
        data = await asyncio.to_thread(Path(argv[2]).read_bytes)
        validated.append(data.decode("utf-8"))
        return CommandResult(0, "", "")

    subject, calls = service(tmp_path, ok_bal)

    await subject.submit_receipt(TRANSACTION)

    # The candidate was validated with `bal` on a temp copy in the append dir,
    # holding the existing content plus the new entry.
    assert len(calls) == 1
    assert calls[0][0] == "hledger"
    assert calls[0][1] == "-f"
    assert calls[0][-1] == "bal"
    validated_file = Path(calls[0][2])
    assert validated_file.parent == tmp_path
    assert validated_file.name.startswith(".receipts.journal.")
    assert validated == [existing + "\n" + render_entry(TRANSACTION)]
    # The temp file is cleaned up, never renamed over the journal.
    assert not await asyncio.to_thread(validated_file.exists)
    # The entry was appended after the existing content.
    expected = (existing + "\n" + render_entry(TRANSACTION)).encode("utf-8")
    assert append.read_bytes() == expected


async def test_submit_creates_a_missing_append_file(tmp_path: Path) -> None:
    subject, _ = service(tmp_path, sync(CommandResult(0, "", "")))

    await subject.submit_receipt(TRANSACTION)

    append = tmp_path / "receipts.journal"
    assert append.read_bytes() == ("\n" + render_entry(TRANSACTION)).encode("utf-8")


async def test_rejected_candidate_is_never_appended(tmp_path: Path) -> None:
    append = tmp_path / "receipts.journal"
    append.write_text(
        "2026-01-01 * K-Market\n    expenses:a  1.00 EUR\n    liabilities:b\n", encoding="utf-8"
    )
    before = append.read_bytes()

    async def reject(argv: list[str]) -> CommandResult:
        return CommandResult(1, "", UNBALANCED_STDERR)

    subject, _ = service(tmp_path, reject)

    with pytest.raises(LedgerRejectedTransactionError, match="unbalanced"):
        await subject.submit_receipt(TRANSACTION)

    assert append.read_bytes() == before


async def test_concurrent_submits_serialize_on_the_lock(tmp_path: Path) -> None:
    async def slow_ok(argv: list[str]) -> CommandResult:
        await asyncio.sleep(0.01)
        return CommandResult(0, "", "")

    subject, calls = service(tmp_path, slow_ok)

    await asyncio.wait_for(
        asyncio.gather(
            subject.submit_receipt(replace(TRANSACTION, receipt_id=1)),
            subject.submit_receipt(replace(TRANSACTION, receipt_id=2)),
        ),
        timeout=10,
    )

    content = (tmp_path / "receipts.journal").read_text("utf-8")
    assert content.count("; receipt-id: 1\n") == 1
    assert content.count("; receipt-id: 2\n") == 1
    assert len(calls) == 2  # each candidate was validated on its own


# --- Error mapping ------------------------------------------------------------


@pytest.mark.parametrize(
    ("result", "error"),
    [
        (
            CommandResult(1, "", 'The hledger journal file "/x" was not found.'),
            LedgerUnavailableError,
        ),
        (
            CommandResult(1, "", "hledger: /x: openFile: permission denied (Permission denied)"),
            LedgerUnavailableError,
        ),
        (CommandResult(1, "", "hledger: Error: unknown command"), LedgerUnavailableError),
        (CommandResult(2, "", "usage: hledger ..."), LedgerUnavailableError),
        (CommandResult(-15, "", ""), LedgerUnavailableError),
        (CommandResult(1, "", UNBALANCED_STDERR), LedgerRejectedTransactionError),
    ],
)
async def test_cli_failures_map_to_ledger_errors(
    tmp_path: Path, result: CommandResult, error: type[Exception]
) -> None:
    subject, _ = service(tmp_path, sync(result))

    with pytest.raises(error) as exc_info:
        await subject.list_accounts()

    if error is LedgerRejectedTransactionError:
        assert "unbalanced" in str(exc_info.value)


async def test_default_runner_reports_a_missing_binary_as_unavailable() -> None:
    with pytest.raises(LedgerUnavailableError) as exc_info:
        await run_hledger_command(["/nonexistent/hledger-binary", "-f", "x", "bal"], 1)

    assert "not found" in exc_info.value.detail


async def test_default_runner_times_out_as_unavailable() -> None:
    with pytest.raises(LedgerUnavailableError) as exc_info:
        await run_hledger_command(["sleep", "5"], 0.1)

    assert "did not answer" in exc_info.value.detail


async def test_default_runner_captures_the_exit_code_and_output() -> None:
    result = await run_hledger_command(["printf", "hello"], 5)

    assert result == CommandResult(0, "hello", "")


# --- Factory ------------------------------------------------------------------


def test_factory_builds_the_beancount_service_by_default() -> None:
    settings = Settings(LEDGER_PROVIDER="beancount")

    subject = build_ledger_service(settings)

    assert isinstance(subject, BeancountLedgerService)
    assert subject.base_url == settings.BEANCOUNT_SERVICE_URL
    assert subject.timeout == settings.BEANCOUNT_TIMEOUT_SECONDS


def test_factory_builds_the_hledger_adapter() -> None:
    settings = Settings(
        LEDGER_PROVIDER="hledger",
        HLEDGER_FILE=Path("journals/current.journal"),
        HLEDGER_APPEND_FILE=Path("journals/receipts.journal"),
        HLEDGER_BINARY="hledger",
        HLEDGER_TIMEOUT_SECONDS=7,
    )

    subject = build_ledger_service(settings)

    assert isinstance(subject, HledgerLedgerService)
    assert subject.read_file == Path("journals/current.journal")
    assert subject.append_file == Path("journals/receipts.journal")
    assert subject.binary == "hledger"
    assert subject.timeout_seconds == 7


def test_hledger_append_file_defaults_to_the_read_file() -> None:
    settings = Settings(LEDGER_PROVIDER="hledger", HLEDGER_FILE=Path("journals/current.journal"))

    subject = build_ledger_service(settings)

    assert isinstance(subject, HledgerLedgerService)
    assert subject.append_file == subject.read_file


def test_factory_fails_fast_when_hledger_has_no_file() -> None:
    with pytest.raises(ValueError, match="HLEDGER_FILE"):
        build_ledger_service(Settings(LEDGER_PROVIDER="hledger"))


# --- Integration: the real binary against a temp journal ----------------------

HLEDGER = shutil.which("hledger")


@pytest.mark.skipif(HLEDGER is None, reason="no hledger binary on PATH")
async def test_real_hledger_binary_reads_and_appends(tmp_path: Path) -> None:
    assert HLEDGER is not None
    read = tmp_path / "current.journal"
    read.write_text(
        "2026-01-01 * K-Market\n"
        "    expenses:groceries  10.00 EUR\n"
        "    liabilities:op:credit-card:gold  -10.00 EUR\n",
        encoding="utf-8",
    )
    append = tmp_path / "receipts.journal"
    subject = HledgerLedgerService(read_file=read, append_file=append, binary=HLEDGER)

    assert (
        LedgerAccount("expenses:groceries", AccountType.EXPENSES) in await subject.list_accounts()
    )
    assert (
        LedgerAccount("liabilities:op:credit-card:gold", AccountType.LIABILITIES)
        in await subject.list_accounts()
    )
    assert await subject.list_payees() == ["K-Market"]

    await subject.submit_receipt(TRANSACTION)

    assert append.read_bytes() == ("\n" + render_entry(TRANSACTION)).encode("utf-8")
    result = await run_hledger_command([HLEDGER, "-f", str(append), "bal"], 10)
    assert result.returncode == 0, result.stderr
