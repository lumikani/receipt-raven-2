from dependency_injector import containers, providers

from src.application.classification.commands.create_rule_use_case import CreateRuleUseCase
from src.application.classification.commands.delete_account_share_default_use_case import (
    DeleteAccountShareDefaultUseCase,
)
from src.application.classification.commands.delete_rule_use_case import DeleteRuleUseCase
from src.application.classification.commands.set_account_share_default_use_case import (
    SetAccountShareDefaultUseCase,
)
from src.application.classification.commands.set_rule_enabled_use_case import SetRuleEnabledUseCase
from src.application.classification.commands.update_rule_use_case import UpdateRuleUseCase
from src.application.classification.queries.get_rule_use_case import GetRuleUseCase
from src.application.classification.queries.list_account_share_defaults_use_case import (
    ListAccountShareDefaultsUseCase,
)
from src.application.classification.queries.list_rules_use_case import ListRulesUseCase


class ClassificationContainer(containers.DeclarativeContainer):
    """Classification module use cases."""

    classification_rule_repository = providers.Dependency()
    account_share_default_repository = providers.Dependency()
    ledger_service = providers.Dependency()

    list_rules_use_case = providers.Factory(
        ListRulesUseCase, rule_repository=classification_rule_repository
    )
    get_rule_use_case = providers.Factory(
        GetRuleUseCase, rule_repository=classification_rule_repository
    )
    create_rule_use_case = providers.Factory(
        CreateRuleUseCase,
        rule_repository=classification_rule_repository,
        ledger_service=ledger_service,
    )
    update_rule_use_case = providers.Factory(
        UpdateRuleUseCase,
        rule_repository=classification_rule_repository,
        ledger_service=ledger_service,
    )
    set_rule_enabled_use_case = providers.Factory(
        SetRuleEnabledUseCase, rule_repository=classification_rule_repository
    )
    delete_rule_use_case = providers.Factory(
        DeleteRuleUseCase, rule_repository=classification_rule_repository
    )
    list_account_share_defaults_use_case = providers.Factory(
        ListAccountShareDefaultsUseCase, repository=account_share_default_repository
    )
    set_account_share_default_use_case = providers.Factory(
        SetAccountShareDefaultUseCase,
        repository=account_share_default_repository,
        ledger_service=ledger_service,
    )
    delete_account_share_default_use_case = providers.Factory(
        DeleteAccountShareDefaultUseCase, repository=account_share_default_repository
    )
