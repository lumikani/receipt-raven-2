from dependency_injector import containers, providers

from src.config import get_settings
from src.containers.analysis import AnalysisContainer
from src.containers.classification import ClassificationContainer
from src.containers.jobs import JobsContainer
from src.containers.ledger import LedgerContainer
from src.containers.receipts import ReceiptsContainer
from src.containers.shared import SharedContainer
from src.database import current_db_session


class RootContainer(containers.DeclarativeContainer):
    """Root DI container composing the module sub-containers."""

    # Resolved per call from the context-bound session rather than overridden on
    # this process-wide container: an override is visible to every concurrent
    # request, so two in flight at once could resolve each other's session.
    db = providers.Callable(current_db_session)

    settings = providers.Object(get_settings())

    shared = providers.Container(SharedContainer, db=db, settings=settings)

    jobs = providers.Container(
        JobsContainer,
        settings=settings,
        receipt_job_repository=shared.receipt_job_repository,
        job_list_query=shared.job_list_query,
        document_storage=shared.document_storage,
        uploads_cleanup=shared.uploads_cleanup,
    )
    ledger = providers.Container(
        LedgerContainer,
        ledger_service=shared.ledger_service,
        account_roles=shared.account_roles,
        settings=settings,
    )
    classification = providers.Container(
        ClassificationContainer,
        classification_rule_repository=shared.classification_rule_repository,
        account_share_default_repository=shared.account_share_default_repository,
        ledger_service=shared.ledger_service,
        settings=settings,
    )
    receipts = providers.Container(
        ReceiptsContainer,
        receipt_repository=shared.receipt_repository,
        receipt_list_query=shared.receipt_list_query,
        ledger_service=shared.ledger_service,
        receipt_classifier=classification.receipt_classifier,
        account_roles=shared.account_roles,
    )
    analysis = providers.Container(
        AnalysisContainer,
        settings=settings,
        receipt_job_repository=shared.receipt_job_repository,
        receipt_repository=shared.receipt_repository,
        document_storage=shared.document_storage,
        receipt_analyzer=shared.receipt_analyzer,
        ledger_service=shared.ledger_service,
        payee_account_rules=shared.payee_account_rules,
        account_roles=shared.account_roles,
        receipt_classifier=classification.receipt_classifier,
    )
