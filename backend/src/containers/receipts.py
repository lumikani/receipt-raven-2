from dependency_injector import containers, providers

from src.application.receipts.commands.approve_receipt_use_case import ApproveReceiptUseCase
from src.application.receipts.commands.create_receipt_use_case import CreateReceiptUseCase
from src.application.receipts.commands.delete_receipt_use_case import DeleteReceiptUseCase
from src.application.receipts.commands.reclassify_all_unapproved_use_case import (
    ReclassifyAllUnapprovedUseCase,
)
from src.application.receipts.commands.reclassify_receipt_use_case import ReclassifyReceiptUseCase
from src.application.receipts.queries.get_receipt_use_case import GetReceiptUseCase
from src.application.receipts.queries.list_receipts_use_case import ListReceiptsUseCase


class ReceiptsContainer(containers.DeclarativeContainer):
    """Receipts module use cases."""

    receipt_repository = providers.Dependency()
    receipt_list_query = providers.Dependency()
    ledger_service = providers.Dependency()
    receipt_classifier = providers.Dependency()
    account_roles = providers.Dependency()

    list_receipts_use_case = providers.Factory(
        ListReceiptsUseCase, receipt_list_query=receipt_list_query
    )
    get_receipt_use_case = providers.Factory(
        GetReceiptUseCase, receipt_repository=receipt_repository
    )
    create_receipt_use_case = providers.Factory(
        CreateReceiptUseCase,
        receipt_repository=receipt_repository,
        receipt_classifier=receipt_classifier,
    )
    approve_receipt_use_case = providers.Factory(
        ApproveReceiptUseCase,
        receipt_repository=receipt_repository,
        ledger_service=ledger_service,
        account_roles=account_roles,
    )
    delete_receipt_use_case = providers.Factory(
        DeleteReceiptUseCase, receipt_repository=receipt_repository
    )
    reclassify_receipt_use_case = providers.Factory(
        ReclassifyReceiptUseCase,
        receipt_repository=receipt_repository,
        receipt_classifier=receipt_classifier,
    )
    reclassify_all_unapproved_use_case = providers.Factory(
        ReclassifyAllUnapprovedUseCase,
        receipt_repository=receipt_repository,
        receipt_classifier=receipt_classifier,
    )
