"""Ledger adapter for hledger: a journal file plus the hledger CLI.

Reads (accounts, payees) run against the read file. `submit_receipt` renders the
entry, validates it on a temp copy of the append file with `hledger bal`
(deliberately no `ordereddates`, so backdated receipts pass), then appends it
with a single atomic `O_APPEND` write under a local `flock` held across the
whole read-validate-append sequence. hledger takes no locks itself; the flock
only serializes this app's adapter instances. The journal is never replaced
with temp+rename.

Error mapping: rc=0 is success; rc=1 with `hledger: Error: <file>:<line>` is a
journal-level rejection (parse error, unbalanced transaction, failed
assertion) and becomes `LedgerRejectedTransactionError`; everything else —
missing binary, missing/unreadable file (`was not found`, `openFile:`,
`permission denied`), signal, timeout, any other rc, rc=1 without a
file:line (CLI misuse) — is `LedgerUnavailableError`.
"""

import asyncio
import contextlib
import fcntl
import os
import re
import tempfile
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import structlog

from src.domain.ledger.account import AccountType, LedgerAccount
from src.domain.ledger.exceptions import LedgerRejectedTransactionError, LedgerUnavailableError
from src.domain.ledger.receipt_transaction import ReceiptTransaction

logger = structlog.get_logger(__name__)

# `hledger: Error: <file>:<line>[-<line>][:<col>]:` at the end of its line — a
# journal-level rejection (parse error, unbalanced transaction, failed
# assertion). An `Error:` line without such a location is CLI misuse.
_REJECTED_ERROR = re.compile(r"hledger: Error: .+:\d+(?:-\d+)?(?::\d+)?:\s*$", re.MULTILINE)

# The append fd's read chunk size and the lock-acquisition retry interval.
_READ_CHUNK_BYTES = 65536
_LOCK_RETRY_SECONDS = 0.05

# hledger's `--types` letters, mapped to the domain's account types.
_ACCOUNT_TYPE_LETTERS = {
    "A": AccountType.ASSETS,
    "C": AccountType.ASSETS,
    "L": AccountType.LIABILITIES,
    "E": AccountType.EQUITY,
    "R": AccountType.INCOME,
    "X": AccountType.EXPENSES,
}


@dataclass(frozen=True)
class CommandResult:
    """One finished CLI invocation."""

    returncode: int
    stdout: str
    stderr: str


CommandRunner = Callable[[Sequence[str]], Awaitable[CommandResult]]
"""Runs argv and reports its exit code and captured output — the test seam."""


async def run_hledger_command(argv: Sequence[str], timeout_seconds: float) -> CommandResult:
    """The default runner: `asyncio.create_subprocess_exec` under a timeout.

    A missing binary, a signal and a timeout are all `LedgerUnavailableError`.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except FileNotFoundError as exc:
        raise LedgerUnavailableError(f"ledger binary not found: {argv[0]}") from exc
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout_seconds)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise LedgerUnavailableError(
            f"{argv[0]} did not answer within {timeout_seconds} seconds"
        ) from exc
    returncode = process.returncode
    if returncode is None:
        raise LedgerUnavailableError(f"{argv[0]} finished without an exit code")
    if returncode < 0:
        raise LedgerUnavailableError(f"{argv[0]} terminated by signal {-returncode}")
    return CommandResult(
        returncode, stdout.decode("utf-8", "replace"), stderr.decode("utf-8", "replace")
    )


def _cents(amount: float) -> Decimal:
    """A money amount as an exact 2-decimal Decimal (no float artifacts)."""
    return Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def render_entry(transaction: ReceiptTransaction) -> str:
    """The receipt as one hledger journal entry; postings stay unmerged.

    Each posting line carries its item names as a comment. When the postings do
    not sum to zero, one balancing line on the source account closes the entry
    (exact 2-decimal arithmetic, dot decimal mark). A txn-level tag records the
    receipt id. No `commodity` directive is ever written.
    """
    header = f"{transaction.receipt_date.isoformat()} * {transaction.payee}"
    if transaction.description:
        header += f" | {transaction.description}"
    lines = [header]
    total = Decimal("0.00")
    for posting in transaction.postings:
        amount = _cents(posting.price)
        total += amount
        line = f"    {posting.expense_account}  {amount:.2f} {transaction.currency}"
        if posting.name:
            line += f"  ; items: {posting.name}"
        lines.append(line)
    if total != 0:
        lines.append(f"    {transaction.source_account}  {-total:.2f} {transaction.currency}")
    lines.append(f"    ; receipt-id: {transaction.receipt_id}")
    return "\n".join(lines) + "\n"


def _read_fd(fd: int) -> bytes:
    """Read the whole file through the (locked) append-file descriptor."""
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while chunk := os.read(fd, _READ_CHUNK_BYTES):
        chunks.append(chunk)
    return b"".join(chunks)


def _remove(path: str) -> None:
    with contextlib.suppress(FileNotFoundError):
        Path(path).unlink()


class HledgerLedgerService:
    """`LedgerServiceProtocol` over a journal file and the hledger CLI."""

    def __init__(
        self,
        *,
        read_file: Path,
        append_file: Path,
        binary: str = "hledger",
        timeout_seconds: float = 10,
        command_runner: CommandRunner | None = None,
    ) -> None:
        self.read_file = read_file
        self.append_file = append_file
        self.binary = binary
        self.timeout_seconds = timeout_seconds
        self._run: CommandRunner = command_runner or (
            lambda argv: run_hledger_command(argv, timeout_seconds)
        )

    def _argv(self, journal: Path, *args: str) -> list[str]:
        return [self.binary, "-f", str(journal), *args]

    async def _run_cli(self, argv: list[str]) -> CommandResult:
        """Run argv and map a non-zero exit to the ledger's error types."""
        result = await self._run(argv)
        if result.returncode == 0:
            return result
        if result.returncode == 1 and _REJECTED_ERROR.search(result.stderr):
            raise LedgerRejectedTransactionError(result.stderr.strip())
        detail = result.stderr.strip()[:500] or "no output"
        raise LedgerUnavailableError(f"{argv[0]} exited with code {result.returncode}: {detail}")

    async def list_accounts(self, account_type: AccountType | None = None) -> list[LedgerAccount]:
        result = await self._run_cli(self._argv(self.read_file, "accounts", "--used", "--types"))
        accounts: list[LedgerAccount] = []
        for line in result.stdout.splitlines():
            name, _, annotation = line.partition(";")
            letter = annotation.strip().removeprefix("type:").strip()
            mapped = _ACCOUNT_TYPE_LETTERS.get(letter)
            if mapped is None:
                logger.warning("ledger_account_type_unknown", account=name.strip(), type=letter)
                continue
            if account_type is not None and mapped is not account_type:
                continue
            accounts.append(LedgerAccount(name=name.strip(), type=mapped))
        return accounts

    async def list_payees(self) -> list[str]:
        result = await self._run_cli(self._argv(self.read_file, "payees"))
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    async def submit_receipt(self, transaction: ReceiptTransaction) -> None:
        # A leading blank line separates the entry from any previous content.
        block = ("\n" + render_entry(transaction)).encode("utf-8")
        try:
            fd = os.open(self.append_file, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o644)
        except OSError as exc:
            raise LedgerUnavailableError(
                f"cannot open the append journal {self.append_file}: {exc}"
            ) from exc
        try:
            await self._lock(fd)
            existing = _read_fd(fd)
            await self._validate(existing, block)
            if os.write(fd, block) != len(block):
                raise OSError(f"short write to {self.append_file}")
        except OSError as exc:
            raise LedgerUnavailableError(f"could not append to {self.append_file}: {exc}") from exc
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        logger.info(
            "ledger_receipt_submitted",
            receipt_id=transaction.receipt_id,
            journal=str(self.append_file),
        )

    async def _lock(self, fd: int) -> None:
        """Take the exclusive flock without blocking the event loop.

        A blocking `flock(LOCK_EX)` would deadlock two concurrent submits in one
        process, so acquire non-blocking and retry while the holder works.
        """
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                await asyncio.sleep(_LOCK_RETRY_SECONDS)

    async def _validate(self, existing: bytes, block: bytes) -> None:
        """`hledger bal` the append file's content plus the candidate entry.

        The temp copy lives in the same directory as the append file; it is only
        ever read by the CLI and deleted afterwards — never renamed over the
        journal.
        """
        fd, tmp_name = tempfile.mkstemp(
            dir=self.append_file.parent, prefix=f".{self.append_file.name}.", suffix=".validate"
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(existing)
                handle.write(block)
            await self._run_cli(self._argv(Path(tmp_name), "bal"))
        finally:
            _remove(tmp_name)
