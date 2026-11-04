"""API routes for receipts.

Routers convert between Pydantic schemas and what the use cases take and
return (primitives in, domain entities or view DTOs out). They hold no logic.
"""

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from src.application.common.pagination import PageRequest
from src.application.receipts.commands.approve_receipt_use_case import ApproveReceiptUseCase
from src.application.receipts.commands.create_receipt_use_case import CreateReceiptUseCase
from src.application.receipts.commands.delete_receipt_use_case import DeleteReceiptUseCase
from src.application.receipts.commands.receipt_fields import ReceiptFields
from src.application.receipts.commands.reclassify_all_unapproved_use_case import (
    ReclassifyAllUnapprovedUseCase,
)
from src.application.receipts.commands.reclassify_receipt_use_case import ReclassifyReceiptUseCase
from src.application.receipts.queries.export_receipts_use_case import ExportReceiptsUseCase
from src.application.receipts.queries.get_receipt_use_case import GetReceiptUseCase
from src.application.receipts.queries.list_receipts_use_case import ListReceiptsUseCase
from src.containers import container
from src.domain.common.value_objects import ReceiptItemId
from src.domain.receipts.entities.receipt import Receipt as ReceiptEntity
from src.domain.receipts.entities.receipt import ReceiptLine, ReceiptStatus
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.documents import document_url
from src.infrastructure.common.schemas import ErrorResponse, PaginatedResponse
from src.infrastructure.common.schemas.pagination import page_request
from src.infrastructure.receipts.export_rendering import render_csv, render_tsv
from src.infrastructure.receipts.schemas import (
    OcrIssue,
    OcrNotes,
    Receipt,
    ReceiptDocument,
    ReceiptItem,
    ReceiptRequest,
    ReceiptStatusValue,
    ReceiptSummary,
    ReclassifyAllResponse,
)

router = APIRouter(prefix="/receipts", tags=["receipts"])

ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "The receipt breaks a business rule"},
    404: {"model": ErrorResponse, "description": "No such receipt"},
}


def receipt_to_schema(receipt: ReceiptEntity) -> Receipt:
    """Convert a Receipt aggregate to its response schema."""
    notes = receipt.ocr_notes
    issue = notes.suspicious_date if notes else None
    return Receipt(
        id=receipt.id.value,
        payee=receipt.payee,
        description=receipt.description,
        date=receipt.receipt_date,
        total_sum=receipt.total_sum,
        currency=receipt.currency,
        status=receipt.status.value,
        booked=receipt.booked,
        source_account=receipt.source_account,
        card_last_digits=receipt.card_last_digits,
        parsed_by=receipt.parsed_by,
        items=[
            ReceiptItem(
                id=item.id.value,
                name=item.name,
                expense_account=item.expense_account,
                price=item.price,
                flatmate_share=item.flatmate_share,
                matched_rule_id=(
                    item.matched_rule_id.value if item.matched_rule_id is not None else None
                ),
                classification_overridden=item.classification_overridden,
            )
            for item in receipt.items
        ],
        ocr_notes=(
            OcrNotes(
                suspicious_date=(
                    OcrIssue(level=issue.level.value, message=issue.message) if issue else None
                )
            )
            if notes
            else None
        ),
        document=(
            ReceiptDocument(
                url=document_url(receipt.document_filename),
                mime_type=receipt.document_mime_type or "application/octet-stream",
            )
            if receipt.document_filename
            else None
        ),
        job_id=receipt.job_id.value if receipt.job_id else None,
        created_at=receipt.created_at,
    )


def request_to_fields(request: ReceiptRequest) -> ReceiptFields:
    return ReceiptFields(
        payee=request.payee,
        receipt_date=request.date,
        total_sum=request.total_sum,
        description=request.description,
        source_account=request.source_account,
        currency=request.currency,
        lines=[
            ReceiptLine(
                name=line.name,
                expense_account=line.expense_account,
                price=line.price,
                item_id=ReceiptItemId(line.id) if line.id is not None else None,
                flatmate_share=line.flatmate_share,
            )
            for line in request.items
        ],
    )


@router.get("", response_model=PaginatedResponse[ReceiptSummary])
async def list_receipts(
    page: PageRequest = Depends(page_request),
    status: Annotated[ReceiptStatusValue | None, Query(description="Only this status")] = None,
    use_case: ListReceiptsUseCase = Depends(
        inject_use_case(container.receipts.list_receipts_use_case)
    ),
) -> PaginatedResponse[ReceiptSummary]:
    result = await use_case.list_receipts(page, ReceiptStatus(status) if status else None)
    return PaginatedResponse(
        items=[
            ReceiptSummary(
                id=view.id,
                payee=view.payee,
                description=view.description,
                date=view.receipt_date,
                total_sum=view.total_sum,
                currency=view.currency,
                status=view.status.value,
                booked=view.booked,
                source_account=view.source_account,
                export_eligible=view.export_eligible,
                item_count=view.item_count,
                has_ocr_issues=view.has_ocr_issues,
                created_at=view.created_at,
            )
            for view in result.items
        ],
        total=result.total,
        offset=result.offset,
        limit=result.limit,
    )


@router.post("", response_model=Receipt, status_code=status.HTTP_201_CREATED, responses=ERRORS)
async def create_receipt(
    request: ReceiptRequest,
    use_case: CreateReceiptUseCase = Depends(
        inject_use_case(container.receipts.create_receipt_use_case)
    ),
) -> Receipt:
    """Store a receipt entered by hand. It starts unapproved."""
    return receipt_to_schema(await use_case.create_receipt(request_to_fields(request)))


@router.post("/reclassify-all-unapproved", response_model=ReclassifyAllResponse, responses=ERRORS)
async def reclassify_all_unapproved(
    use_case: ReclassifyAllUnapprovedUseCase = Depends(
        inject_use_case(container.receipts.reclassify_all_unapproved_use_case)
    ),
) -> ReclassifyAllResponse:
    """Re-run the classification rules on every unapproved receipt."""
    receipts = await use_case.reclassify_all_unapproved()
    return ReclassifyAllResponse(receipt_ids=[receipt.id.value for receipt in receipts])


def parse_ids(raw: str | None) -> frozenset[int] | None:
    """Parse the `ids=1,2,3` query parameter; blank means no id filter."""
    if raw is None or not raw.strip():
        return None
    try:
        return frozenset(int(part.strip()) for part in raw.split(",") if part.strip())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="ids must be a comma-separated list of receipt ids",
        ) from None


# Declared before GET /receipts/{receipt_id} so `export.csv` is not swallowed
# by the path parameter.
@router.get(
    "/export.csv",
    response_class=Response,
    responses={
        200: {
            "description": (
                "The balancing export: one row per eligible approved personal-card "
                "receipt. `;`-delimited comma-decimal CSV with a header row, or "
                "headerless tab-separated TSV with `format=tsv`."
            ),
            "content": {
                "text/csv": {"schema": {"type": "string", "format": "binary"}},
                "text/tab-separated-values": {"schema": {"type": "string", "format": "binary"}},
            },
        },
        422: {"model": ErrorResponse, "description": "Malformed selection parameters"},
    },
)
async def export_receipts(
    ids: Annotated[str | None, Query(description="Comma-separated receipt ids to include")] = None,
    from_date: Annotated[
        date | None, Query(alias="from", description="First receipt date, inclusive")
    ] = None,
    to_date: Annotated[
        date | None, Query(alias="to", description="Last receipt date, inclusive")
    ] = None,
    format: Literal["csv", "tsv"] = "csv",
    use_case: ExportReceiptsUseCase = Depends(
        inject_use_case(container.receipts.export_receipts_use_case)
    ),
) -> Response:
    """Download the balancing export, or its headerless TSV variant for Sheets.

    Eligibility (approved, personal card, bookable currency, at least one item
    with a flatmate share) is always applied; the selection only narrows it.
    """
    rows = await use_case.export_receipts(ids=parse_ids(ids), from_date=from_date, to_date=to_date)
    if format == "tsv":
        return Response(
            content=render_tsv(rows),
            media_type="text/tab-separated-values",
            headers={"Content-Disposition": 'attachment; filename="receipts-export.tsv"'},
        )
    return Response(
        content=render_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="receipts-export.csv"'},
    )


@router.get("/{receipt_id}", response_model=Receipt, responses=ERRORS)
async def get_receipt(
    receipt_id: int,
    use_case: GetReceiptUseCase = Depends(inject_use_case(container.receipts.get_receipt_use_case)),
) -> Receipt:
    return receipt_to_schema(await use_case.get_receipt(receipt_id))


@router.post(
    "/{receipt_id}/approve",
    response_model=Receipt,
    responses={
        **ERRORS,
        502: {"model": ErrorResponse, "description": "The ledger is down or rejected it"},
    },
)
async def approve_receipt(
    receipt_id: int,
    request: ReceiptRequest,
    use_case: ApproveReceiptUseCase = Depends(
        inject_use_case(container.receipts.approve_receipt_use_case)
    ),
) -> Receipt:
    """Save the edited receipt and write it to the ledger.

    The edits are kept even when the ledger refuses the receipt.
    """
    receipt = await use_case.approve_receipt(receipt_id, request_to_fields(request))
    return receipt_to_schema(receipt)


@router.post("/{receipt_id}/reclassify", response_model=Receipt, responses=ERRORS)
async def reclassify_receipt(
    receipt_id: int,
    use_case: ReclassifyReceiptUseCase = Depends(
        inject_use_case(container.receipts.reclassify_receipt_use_case)
    ),
) -> Receipt:
    """Re-run the classification rules on this receipt.

    Items whose account or share was edited manually are overrides and keep
    their values. Approved receipts are immutable.
    """
    return receipt_to_schema(await use_case.reclassify_receipt(receipt_id))


@router.delete("/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
async def delete_receipt(
    receipt_id: int,
    use_case: DeleteReceiptUseCase = Depends(
        inject_use_case(container.receipts.delete_receipt_use_case)
    ),
) -> None:
    await use_case.delete_receipt(receipt_id)
