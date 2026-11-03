"""Use case run by the analysis worker: turn the next waiting upload into a receipt."""

from collections.abc import Callable
from datetime import UTC, date, datetime

import structlog

from src.application.analysis.protocols.payee_account_rules import (
    PayeeAccountRulesProviderProtocol,
)
from src.application.analysis.protocols.receipt_analyzer import (
    ReceiptAnalysis,
    ReceiptAnalyzerProtocol,
)
from src.application.classification.protocols.receipt_classifier import (
    ReceiptClassifierProtocol,
)
from src.application.jobs.protocols.document_storage import DocumentStorageProtocol
from src.application.jobs.protocols.receipt_job_repository import ReceiptJobRepositoryProtocol
from src.application.ledger.protocols.ledger_service import LedgerServiceProtocol
from src.application.receipts.protocols.receipt_repository import ReceiptRepositoryProtocol
from src.domain.jobs.entities.receipt_job import ReceiptJob
from src.domain.ledger.account import AccountType
from src.domain.receipts.entities.receipt import Receipt, ReceiptLine
from src.domain.receipts.services.heuristics import run_heuristics

logger = structlog.get_logger(__name__)


def local_today() -> date:
    """Today in the server's time zone: receipts are dated in local time."""
    return datetime.now(UTC).astimezone().date()


class ProcessNextJobUseCase:
    """Analyse the oldest waiting document and store the receipt it shows.

    The steps, in order: read the document, fetch the expense accounts the model
    may choose from, analyse, flag a suspicious date, pick the source account by
    the payee rules (falling back to the configured default), stamp every item
    with the classification rules, store the receipt. Any failure is recorded
    on the job, which is retried until it runs out of attempts.
    """

    def __init__(
        self,
        *,
        job_repository: ReceiptJobRepositoryProtocol,
        receipt_repository: ReceiptRepositoryProtocol,
        document_storage: DocumentStorageProtocol,
        receipt_analyzer: ReceiptAnalyzerProtocol,
        ledger_service: LedgerServiceProtocol,
        payee_account_rules: PayeeAccountRulesProviderProtocol,
        receipt_classifier: ReceiptClassifierProtocol,
        max_attempts: int,
        default_source_account: str | None,
        today: Callable[[], date] = local_today,
    ) -> None:
        self.job_repository = job_repository
        self.receipt_repository = receipt_repository
        self.document_storage = document_storage
        self.receipt_analyzer = receipt_analyzer
        self.ledger_service = ledger_service
        self.payee_account_rules = payee_account_rules
        self.receipt_classifier = receipt_classifier
        self.max_attempts = max_attempts
        self.default_source_account = default_source_account
        self.today = today

    async def process_next_job(self) -> ReceiptJob | None:
        """Process one job. Returns it, or None when no job is waiting."""
        job = await self.job_repository.find_next_waiting()
        if job is None:
            return None

        log = logger.bind(job_id=job.id.value)
        try:
            receipt = await self._analyse(job)
            await self.receipt_repository.save(receipt)
            job.mark_processed()
            log.info("receipt_job_processed")
        except Exception as exc:
            job.record_failure(f"Receipt analysis failed: {exc}", self.max_attempts)
            log.warning("receipt_job_failed", error=str(exc), attempts=job.retry_count)
        return await self.job_repository.save(job)

    async def _analyse(self, job: ReceiptJob) -> Receipt:
        document = await self.document_storage.read(job.filename)
        accounts = await self.ledger_service.list_accounts(AccountType.EXPENSES)
        analysis = await self.receipt_analyzer.analyze(
            document, job.mime_type, [account.name for account in accounts]
        )
        receipt = self._to_receipt(job, analysis)
        # Snapshot: every item is stamped with account, share and rule id now;
        # later rule changes only apply through the manual re-classify actions.
        await self.receipt_classifier.stamp_receipt(receipt)
        return receipt

    def _to_receipt(self, job: ReceiptJob, analysis: ReceiptAnalysis) -> Receipt:
        today = self.today()
        receipt_date = analysis.receipt_date or today
        rule = self.payee_account_rules.load().source_account_for(analysis.payee)
        if rule is not None:
            logger.info("payee_rule_matched", payee=analysis.payee, account=rule.source_account)
        return Receipt.create_from_analysis(
            job_id=job.id,
            document_filename=job.filename,
            document_mime_type=job.mime_type,
            payee=analysis.payee,
            receipt_date=receipt_date,
            total_sum=analysis.total,
            lines=[
                ReceiptLine(name=p.name, expense_account=p.expense_account, price=p.price)
                for p in analysis.products
            ],
            parsed_by=analysis.model,
            ocr_notes=run_heuristics(receipt_date, today),
            description=analysis.description,
            source_account=rule.source_account if rule else self.default_source_account,
            currency=analysis.currency,
            card_last_digits=analysis.card_last_digits,
        )
