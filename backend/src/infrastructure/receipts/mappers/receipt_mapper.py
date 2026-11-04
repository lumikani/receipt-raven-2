"""Mapper for Receipt ORM <-> domain conversion."""

from typing import Any

from src.domain.common.value_objects import (
    ClassificationRuleId,
    ReceiptId,
    ReceiptItemId,
    ReceiptJobId,
)
from src.domain.receipts.entities.receipt import Receipt, ReceiptItem, ReceiptStatus
from src.domain.receipts.ocr_notes import HeuristicIssue, HeuristicLevel, OcrNotes
from src.infrastructure.common.mappers import orm_id
from src.infrastructure.receipts.orm.receipt_model import ReceiptItemModel, ReceiptModel


def ocr_notes_to_json(notes: OcrNotes | None) -> dict[str, Any] | None:
    if notes is None:
        return None
    issue = notes.suspicious_date
    return {
        "suspicious_date": (
            {"level": issue.level.value, "message": issue.message} if issue else None
        )
    }


def ocr_notes_from_json(data: dict[str, Any] | None) -> OcrNotes | None:
    if data is None:
        return None
    issue = data.get("suspicious_date")
    return OcrNotes(
        suspicious_date=(
            HeuristicIssue(level=HeuristicLevel(issue["level"]), message=str(issue["message"]))
            if isinstance(issue, dict)
            else None
        )
    )


class ReceiptMapper:
    """Convert between the Receipt aggregate and its rows."""

    def to_domain(self, orm_model: ReceiptModel) -> Receipt:
        return Receipt(
            id=ReceiptId(orm_model.id),
            payee=orm_model.payee,
            receipt_date=orm_model.receipt_date,
            total_sum=orm_model.total_sum,
            items=[
                ReceiptItem(
                    id=ReceiptItemId(item.id),
                    name=item.name,
                    expense_account=item.expense_account,
                    price=item.price,
                    parsed_by=item.parsed_by,
                    flatmate_share=item.flatmate_share,
                    matched_rule_id=(
                        ClassificationRuleId(item.matched_rule_id)
                        if item.matched_rule_id is not None
                        else None
                    ),
                    classification_overridden=item.classification_overridden,
                )
                for item in orm_model.items
            ],
            parsed_by=orm_model.parsed_by,
            description=orm_model.description,
            source_account=orm_model.source_account,
            currency=orm_model.currency,
            status=ReceiptStatus(orm_model.status),
            booked=orm_model.booked,
            card_last_digits=orm_model.card_last_digits,
            job_id=ReceiptJobId(orm_model.job_id) if orm_model.job_id is not None else None,
            document_filename=orm_model.document_filename,
            document_mime_type=orm_model.document_mime_type,
            ocr_notes=ocr_notes_from_json(orm_model.ocr_notes),
            created_at=orm_model.created_at,
        )

    def to_orm(self, domain_entity: Receipt, orm_model: ReceiptModel | None = None) -> ReceiptModel:
        if orm_model is None:
            orm_model = ReceiptModel(id=orm_id(domain_entity.id), items=[])
        orm_model.job_id = domain_entity.job_id.value if domain_entity.job_id else None
        orm_model.payee = domain_entity.payee
        orm_model.receipt_date = domain_entity.receipt_date
        orm_model.description = domain_entity.description
        orm_model.total_sum = domain_entity.total_sum
        orm_model.currency = domain_entity.currency
        orm_model.parsed_by = domain_entity.parsed_by
        orm_model.source_account = domain_entity.source_account
        orm_model.status = domain_entity.status.value
        orm_model.booked = domain_entity.booked
        orm_model.card_last_digits = domain_entity.card_last_digits
        orm_model.document_filename = domain_entity.document_filename
        orm_model.document_mime_type = domain_entity.document_mime_type
        orm_model.ocr_notes = ocr_notes_to_json(domain_entity.ocr_notes)
        orm_model.created_at = domain_entity.created_at
        self._sync_items(domain_entity, orm_model)
        return orm_model

    @staticmethod
    def _sync_items(receipt: Receipt, orm_model: ReceiptModel) -> None:
        """Update rows in place, add new ones, and let delete-orphan drop the rest."""
        existing = {row.id: row for row in orm_model.items}
        rows: list[ReceiptItemModel] = []
        for position, item in enumerate(receipt.items):
            row = existing.get(item.id.value) or ReceiptItemModel(id=orm_id(item.id))
            row.position = position
            row.name = item.name
            row.expense_account = item.expense_account
            row.price = item.price
            row.parsed_by = item.parsed_by
            row.flatmate_share = item.flatmate_share
            row.matched_rule_id = (
                item.matched_rule_id.value if item.matched_rule_id is not None else None
            )
            row.classification_overridden = item.classification_overridden
            rows.append(row)
        orm_model.items = rows
