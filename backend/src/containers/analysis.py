from dependency_injector import containers, providers

from src.application.analysis.commands.process_next_job_use_case import ProcessNextJobUseCase


class AnalysisContainer(containers.DeclarativeContainer):
    """Analysis module use cases, run by the background worker."""

    settings = providers.Dependency()
    receipt_job_repository = providers.Dependency()
    receipt_repository = providers.Dependency()
    document_storage = providers.Dependency()
    receipt_analyzer = providers.Dependency()
    ledger_service = providers.Dependency()
    payee_account_rules = providers.Dependency()
    account_roles = providers.Dependency()
    receipt_classifier = providers.Dependency()

    process_next_job_use_case = providers.Factory(
        ProcessNextJobUseCase,
        job_repository=receipt_job_repository,
        receipt_repository=receipt_repository,
        document_storage=document_storage,
        receipt_analyzer=receipt_analyzer,
        ledger_service=ledger_service,
        payee_account_rules=payee_account_rules,
        account_roles=account_roles,
        receipt_classifier=receipt_classifier,
        max_attempts=settings.provided.MAX_JOB_ATTEMPTS,
        default_source_account=settings.provided.DEFAULT_SOURCE_ACCOUNT,
    )
