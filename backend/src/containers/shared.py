from dependency_injector import containers, providers

from src.application.receipts.commands.approve_receipt_use_case import BOOKABLE_CURRENCIES
from src.infrastructure.analysis.analyzer_factory import build_receipt_analyzer
from src.infrastructure.analysis.payee_account_rules_file import PayeeAccountRulesFile
from src.infrastructure.classification.repositories.account_share_default_repository import (
    AccountShareDefaultRepository,
)
from src.infrastructure.classification.repositories.classification_rule_repository import (
    ClassificationRuleRepository,
)
from src.infrastructure.jobs.queries.job_list_query import JobListQuery
from src.infrastructure.jobs.repositories.receipt_job_repository import ReceiptJobRepository
from src.infrastructure.jobs.storage.local_document_storage import LocalDocumentStorage
from src.infrastructure.jobs.storage.uploads_cleanup import UploadsCleanup
from src.infrastructure.ledger.account_roles_file import AccountRolesFile
from src.infrastructure.ledger.ledger_service_factory import build_ledger_service
from src.infrastructure.receipts.queries.receipt_list_query import ReceiptListQuery
from src.infrastructure.receipts.repositories.receipt_repository import ReceiptRepository


class SharedContainer(containers.DeclarativeContainer):
    """Infrastructure adapters (repositories, query adapters, services).

    Adapters live here rather than in their module's container so that any
    module's use cases can be given any adapter they need.
    """

    db = providers.Dependency()
    settings = providers.Dependency()

    # Repositories
    receipt_repository = providers.Factory(ReceiptRepository, db=db)
    receipt_job_repository = providers.Factory(ReceiptJobRepository, db=db)
    classification_rule_repository = providers.Factory(ClassificationRuleRepository, db=db)
    account_share_default_repository = providers.Factory(AccountShareDefaultRepository, db=db)

    # Query adapters (read models)
    job_list_query = providers.Factory(JobListQuery, db=db)

    # Services: stateless or process-wide, so one instance serves every request
    document_storage = providers.Singleton(
        LocalDocumentStorage, directory=settings.provided.UPLOADS_DIR
    )
    uploads_cleanup = providers.Singleton(
        UploadsCleanup,
        directory=settings.provided.UPLOADS_DIR,
        max_disk_size=settings.provided.MAX_UPLOADS_DISK_SIZE,
    )
    ledger_service = providers.Singleton(build_ledger_service, settings=settings)
    receipt_analyzer = providers.Singleton(build_receipt_analyzer, settings=settings)
    payee_account_rules = providers.Singleton(
        PayeeAccountRulesFile, path=settings.provided.PAYEE_ACCOUNT_RULES_PATH
    )
    account_roles = providers.Singleton(AccountRolesFile, path=settings.provided.ACCOUNT_ROLES_PATH)

    # Needs account_roles, so it is declared after it.
    receipt_list_query = providers.Factory(
        ReceiptListQuery,
        db=db,
        account_roles=account_roles,
        bookable_currencies=BOOKABLE_CURRENCIES,
    )
