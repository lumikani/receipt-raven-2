"""API tests for uploads and the analysis queue, worker included."""

import json
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path
from typing import Any

from dependency_injector import providers
from httpx import AsyncClient

from src.application.analysis.commands.process_next_job_use_case import local_today
from src.containers import container
from src.domain.jobs.entities.receipt_job import ReceiptJob
from src.domain.ledger.account_roles import AccountRoles
from src.infrastructure.analysis.payee_account_rules_file import PayeeAccountRulesFile
from tests.fakes import FakeAccountRoles, FakeLedger, FakeReceiptAnalyzer, analysis

JOBS = "/api/v1/jobs"
RECEIPTS = "/api/v1/receipts"
PHOTO = b"\xff\xd8\xff\xe0 fake jpeg"

RunWorker = Callable[[], Awaitable[ReceiptJob | None]]


def payee_rules_file(tmp_path: Path, *rules: dict[str, str]) -> Path:
    """Write a payee-account-rules JSON file with the given rules."""
    path = tmp_path / "payee-account-rules.json"
    path.write_text(json.dumps({"rules": list(rules)}))
    return path


CARD_ROLES = AccountRoles(
    personal_cards=("Liabilities:CreditCard",),
    shared_card="Liabilities:SharedAccount",
    flatmate_expense_adjustment="Expenses:FlatmateAdjustment",
    purchase_for_flatmate="Expenses:PurchaseForFlatmate",
    card_last_digits=(
        ("9841", "Liabilities:CreditCard"),
        ("0244", "Liabilities:SharedAccount"),
    ),
)


async def upload(
    client: AsyncClient,
    filename: str = "camera capture.jpg",
    content: bytes = PHOTO,
    mime_type: str = "image/jpeg",
) -> dict[str, Any]:
    response = await client.post(JOBS, files={"file": (filename, content, mime_type)})
    assert response.status_code == 201, response.text
    return response.json()


async def only_receipt(client: AsyncClient) -> dict[str, Any]:
    [summary] = (await client.get(RECEIPTS)).json()["items"]
    return (await client.get(f"{RECEIPTS}/{summary['id']}")).json()


class TestUpload:
    async def test_queues_the_document_and_serves_it_back(
        self, client: AsyncClient, uploads_dir: Path
    ) -> None:
        job = await upload(client)

        assert job["status"] == "waiting"
        assert job["retry_count"] == 0
        assert job["filename"].endswith("-camera_capture.jpg")
        assert (uploads_dir / job["filename"]).read_bytes() == PHOTO
        listed = (await client.get(JOBS)).json()
        assert [j["id"] for j in listed["items"]] == [job["id"]]
        document = await client.get(job["document_url"])
        assert document.status_code == 200
        assert document.content == PHOTO

    async def test_accepts_pdf(self, client: AsyncClient) -> None:
        job = await upload(client, "lasku.pdf", b"%PDF-1.4", "application/pdf")

        assert job["mime_type"] == "application/pdf"

    async def test_rejects_other_file_types(self, client: AsyncClient) -> None:
        response = await client.post(JOBS, files={"file": ("notes.txt", b"hi", "text/plain")})

        assert response.status_code == 400
        assert response.json()["message"] == "Upload a photo or a PDF of the receipt"
        assert (await client.get(JOBS)).json()["total"] == 0

    async def test_strips_directories_from_the_filename(
        self, client: AsyncClient, uploads_dir: Path
    ) -> None:
        job = await upload(client, filename="../../etc/passwd.png")

        assert "/" not in job["filename"]
        assert (uploads_dir / job["filename"]).is_file()

    async def test_unknown_document_is_not_found(self, client: AsyncClient) -> None:
        assert (await client.get("/api/v1/documents/missing.jpg")).status_code == 404
        assert (await client.get("/api/v1/documents/..%2Fsecret")).status_code == 404


class TestAnalysis:
    async def test_turns_an_upload_into_an_unapproved_receipt(
        self,
        client: AsyncClient,
        run_worker: RunWorker,
        analyzer: FakeReceiptAnalyzer,
    ) -> None:
        job = await upload(client)

        await run_worker()

        receipt = await only_receipt(client)
        assert receipt["payee"] == "K-Market"
        assert receipt["status"] == "unapproved"
        assert receipt["parsed_by"] == "fake-model"
        assert receipt["job_id"] == job["id"]
        assert receipt["document"] == {"url": job["document_url"], "mime_type": "image/jpeg"}
        assert [(i["name"], i["expense_account"], i["price"]) for i in receipt["items"]] == [
            ("Banaani", "Expenses:Groceries", 0.8),
            ("T-paita", "Expenses:Clothes", 14.99),
        ]
        # An unreadable date falls back to today, which is not suspicious.
        assert receipt["date"] == local_today().isoformat()
        assert receipt["ocr_notes"] == {"suspicious_date": None}
        assert analyzer.offered_accounts == [["Expenses:Groceries", "Expenses:Clothes"]]
        [processed] = (await client.get(JOBS)).json()["items"]
        assert processed["status"] == "processed"
        assert processed["processed_at"] is not None

    async def test_flags_a_date_from_another_year(
        self, client: AsyncClient, run_worker: RunWorker, analyzer: FakeReceiptAnalyzer
    ) -> None:
        analyzer.result = analysis(receipt_date=date(2020, 3, 15))
        await upload(client)

        await run_worker()

        receipt = await only_receipt(client)
        assert receipt["ocr_notes"] == {
            "suspicious_date": {"level": "SEVERE", "message": "Date is in previous year (2020)"}
        }
        assert (await client.get(RECEIPTS)).json()["items"][0]["has_ocr_issues"] is True

    async def test_payee_rules_pick_the_source_account(
        self,
        client: AsyncClient,
        run_worker: RunWorker,
        analyzer: FakeReceiptAnalyzer,
        tmp_path: Path,
    ) -> None:
        rules_file = payee_rules_file(
            tmp_path,
            {"payeePattern": ".*S-Market.*|.*Prisma.*", "sourceAccount": "Assets:Cash"},
            {"payeePattern": "prisma", "sourceAccount": "Assets:Never"},
        )
        analyzer.result = analysis(payee="PRISMA Kaleva")
        await upload(client)

        with container.shared.payee_account_rules.override(
            providers.Object(PayeeAccountRulesFile(rules_file))
        ):
            await run_worker()

        assert (await only_receipt(client))["source_account"] == "Assets:Cash"

    async def test_card_last_digits_pick_the_source_account(
        self,
        client: AsyncClient,
        run_worker: RunWorker,
        analyzer: FakeReceiptAnalyzer,
        account_roles: FakeAccountRoles,
    ) -> None:
        account_roles.roles = CARD_ROLES
        analyzer.result = analysis(card_last_digits="9841")
        await upload(client)

        await run_worker()

        receipt = await only_receipt(client)
        assert receipt["source_account"] == "Liabilities:CreditCard"
        assert receipt["card_last_digits"] == "9841"

    async def test_card_last_digits_beat_the_payee_rules(
        self,
        client: AsyncClient,
        run_worker: RunWorker,
        analyzer: FakeReceiptAnalyzer,
        account_roles: FakeAccountRoles,
        tmp_path: Path,
    ) -> None:
        rules_file = payee_rules_file(
            tmp_path, {"payeePattern": ".*", "sourceAccount": "Assets:Cash"}
        )
        account_roles.roles = CARD_ROLES
        analyzer.result = analysis(payee="PRISMA Kaleva", card_last_digits="0244")
        await upload(client)

        with container.shared.payee_account_rules.override(
            providers.Object(PayeeAccountRulesFile(rules_file))
        ):
            await run_worker()

        assert (await only_receipt(client))["source_account"] == "Liabilities:SharedAccount"

    async def test_unknown_card_digits_never_fall_back_to_the_payee_rules(
        self,
        client: AsyncClient,
        run_worker: RunWorker,
        analyzer: FakeReceiptAnalyzer,
        account_roles: FakeAccountRoles,
        tmp_path: Path,
    ) -> None:
        # The payee name says nothing about which card was used, so a receipt
        # that shows an unrecognized card is not routed by the payee rules.
        rules_file = payee_rules_file(
            tmp_path, {"payeePattern": ".*", "sourceAccount": "Assets:Cash"}
        )
        account_roles.roles = CARD_ROLES
        analyzer.result = analysis(payee="PRISMA Kaleva", card_last_digits="0000")
        await upload(client)

        with container.shared.payee_account_rules.override(
            providers.Object(PayeeAccountRulesFile(rules_file))
        ):
            await run_worker()

        receipt = await only_receipt(client)
        assert receipt["source_account"] is None
        assert receipt["card_last_digits"] == "0000"

    async def test_unknown_card_digits_and_no_rules_leave_the_source_account_unset(
        self,
        client: AsyncClient,
        run_worker: RunWorker,
        analyzer: FakeReceiptAnalyzer,
        account_roles: FakeAccountRoles,
    ) -> None:
        account_roles.roles = CARD_ROLES
        analyzer.result = analysis(card_last_digits="0000")
        await upload(client)

        await run_worker()

        receipt = await only_receipt(client)
        assert receipt["source_account"] is None
        assert receipt["card_last_digits"] == "0000"

    async def test_keeps_the_currency_the_receipt_is_in(
        self, client: AsyncClient, run_worker: RunWorker, analyzer: FakeReceiptAnalyzer
    ) -> None:
        analyzer.result = analysis(
            payee="Lawson",
            products=(("Onigiri", "Expenses:Groceries", 180),),
            total=180,
            currency="JPY",
        )
        await upload(client)

        await run_worker()

        receipt = await only_receipt(client)
        assert (receipt["currency"], receipt["total_sum"]) == ("JPY", 180)

    async def test_does_nothing_when_no_job_is_waiting(self, run_worker: RunWorker) -> None:
        assert await run_worker() is None


class TestFailureAndRetry:
    async def test_failed_job_is_retried_then_given_up_then_retried_by_hand(
        self,
        client: AsyncClient,
        run_worker: RunWorker,
        analyzer: FakeReceiptAnalyzer,
    ) -> None:
        job = await upload(client)
        analyzer.error = "model overloaded"

        await run_worker()
        [after_one] = (await client.get(JOBS)).json()["items"]
        await run_worker()
        await run_worker()
        [after_three] = (await client.get(JOBS)).json()["items"]

        assert (after_one["status"], after_one["retry_count"]) == ("waiting", 1)
        assert after_one["analysis_error"] == "Receipt analysis failed: model overloaded"
        assert (after_three["status"], after_three["retry_count"]) == ("failed", 3)
        assert await run_worker() is None

        retried = await client.post(f"{JOBS}/{job['id']}/retry")
        analyzer.error = None
        await run_worker()

        assert retried.status_code == 200
        assert (retried.json()["status"], retried.json()["retry_count"]) == ("waiting", 0)
        assert retried.json()["analysis_error"] is None
        assert (await client.get(RECEIPTS)).json()["total"] == 1

    async def test_unavailable_ledger_fails_the_attempt(
        self, client: AsyncClient, run_worker: RunWorker, ledger: FakeLedger
    ) -> None:
        await upload(client)
        ledger.unavailable = True

        job = await run_worker()

        assert job is not None
        assert job.retry_count == 1
        assert "ledger service is not available" in (job.analysis_error or "")

    async def test_unknown_job_is_not_found(self, client: AsyncClient) -> None:
        assert (await client.post(f"{JOBS}/999/retry")).status_code == 404

    async def test_only_failed_jobs_can_be_retried(self, client: AsyncClient) -> None:
        job = await upload(client)

        response = await client.post(f"{JOBS}/{job['id']}/retry")

        assert response.status_code == 409
        assert response.json()["message"] == "Only a failed job can be retried"
