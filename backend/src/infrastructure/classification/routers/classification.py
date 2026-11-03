"""API routes for classification rules and account share defaults.

Routers convert between Pydantic schemas and what the use cases take and
return. They hold no logic.
"""

from typing import Any

from fastapi import APIRouter, Depends, status

from src.application.classification.commands.create_rule_use_case import CreateRuleUseCase
from src.application.classification.commands.delete_account_share_default_use_case import (
    DeleteAccountShareDefaultUseCase,
)
from src.application.classification.commands.delete_rule_use_case import DeleteRuleUseCase
from src.application.classification.commands.rule_fields import RuleFields
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
from src.containers import container
from src.domain.classification.entities.account_share_default import (
    AccountShareDefault as AccountShareDefaultEntity,
)
from src.domain.classification.entities.classification_rule import (
    ClassificationRule as ClassificationRuleEntity,
)
from src.infrastructure.classification.schemas import (
    AccountShareDefault,
    AccountShareDefaultRequest,
    ClassificationRule,
    ClassificationRuleRequest,
    SetRuleEnabledRequest,
)
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import CollectionResponse, ErrorResponse

router = APIRouter(prefix="/classification", tags=["classification"])

ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "The request breaks a business rule"},
    404: {"model": ErrorResponse, "description": "No such rule or account default"},
    409: {"model": ErrorResponse, "description": "The normalized pattern already exists"},
    502: {"model": ErrorResponse, "description": "The ledger is not available"},
}


def rule_to_schema(rule: ClassificationRuleEntity) -> ClassificationRule:
    return ClassificationRule(
        id=rule.id.value,
        pattern=rule.pattern,
        normalized_pattern=rule.normalized_pattern,
        max_typos=rule.max_typos,
        expense_account=rule.expense_account,
        flatmate_share_override=rule.flatmate_share_override,
        enabled=rule.enabled,
        created_at=rule.created_at,
    )


def share_default_to_schema(default: AccountShareDefaultEntity) -> AccountShareDefault:
    return AccountShareDefault(
        id=default.id.value,
        expense_account=default.expense_account,
        share=default.share,
        created_at=default.created_at,
    )


def request_to_fields(request: ClassificationRuleRequest) -> RuleFields:
    return RuleFields(
        pattern=request.pattern,
        max_typos=request.max_typos,
        expense_account=request.expense_account,
        flatmate_share_override=request.flatmate_share_override,
        enabled=request.enabled,
    )


@router.get("/rules", response_model=CollectionResponse[ClassificationRule])
async def list_rules(
    use_case: ListRulesUseCase = Depends(
        inject_use_case(container.classification.list_rules_use_case)
    ),
) -> CollectionResponse[ClassificationRule]:
    rules = await use_case.list_rules()
    return CollectionResponse(items=[rule_to_schema(rule) for rule in rules])


@router.post(
    "/rules",
    response_model=ClassificationRule,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
async def create_rule(
    request: ClassificationRuleRequest,
    use_case: CreateRuleUseCase = Depends(
        inject_use_case(container.classification.create_rule_use_case)
    ),
) -> ClassificationRule:
    return rule_to_schema(await use_case.create_rule(request_to_fields(request)))


@router.get("/rules/{rule_id}", response_model=ClassificationRule, responses=ERRORS)
async def get_rule(
    rule_id: int,
    use_case: GetRuleUseCase = Depends(inject_use_case(container.classification.get_rule_use_case)),
) -> ClassificationRule:
    return rule_to_schema(await use_case.get_rule(rule_id))


@router.put("/rules/{rule_id}", response_model=ClassificationRule, responses=ERRORS)
async def update_rule(
    rule_id: int,
    request: ClassificationRuleRequest,
    use_case: UpdateRuleUseCase = Depends(
        inject_use_case(container.classification.update_rule_use_case)
    ),
) -> ClassificationRule:
    return rule_to_schema(await use_case.update_rule(rule_id, request_to_fields(request)))


@router.post("/rules/{rule_id}/set-enabled", response_model=ClassificationRule, responses=ERRORS)
async def set_rule_enabled(
    rule_id: int,
    request: SetRuleEnabledRequest,
    use_case: SetRuleEnabledUseCase = Depends(
        inject_use_case(container.classification.set_rule_enabled_use_case)
    ),
) -> ClassificationRule:
    """Enable or disable a rule; disabled rules never match."""
    return rule_to_schema(await use_case.set_rule_enabled(rule_id, request.enabled))


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
async def delete_rule(
    rule_id: int,
    use_case: DeleteRuleUseCase = Depends(
        inject_use_case(container.classification.delete_rule_use_case)
    ),
) -> None:
    await use_case.delete_rule(rule_id)


@router.get("/account-share-defaults", response_model=CollectionResponse[AccountShareDefault])
async def list_account_share_defaults(
    use_case: ListAccountShareDefaultsUseCase = Depends(
        inject_use_case(container.classification.list_account_share_defaults_use_case)
    ),
) -> CollectionResponse[AccountShareDefault]:
    defaults = await use_case.list_account_share_defaults()
    return CollectionResponse(items=[share_default_to_schema(d) for d in defaults])


@router.put(
    "/account-share-defaults",
    response_model=AccountShareDefault,
    status_code=status.HTTP_200_OK,
    responses=ERRORS,
)
async def set_account_share_default(
    request: AccountShareDefaultRequest,
    use_case: SetAccountShareDefaultUseCase = Depends(
        inject_use_case(container.classification.set_account_share_default_use_case)
    ),
) -> AccountShareDefault:
    """Create or update one account's default flatmate share."""
    default = await use_case.set_account_share_default(request.expense_account, request.share)
    return share_default_to_schema(default)


@router.delete(
    "/account-share-defaults/{expense_account}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERRORS,
)
async def delete_account_share_default(
    expense_account: str,
    use_case: DeleteAccountShareDefaultUseCase = Depends(
        inject_use_case(container.classification.delete_account_share_default_use_case)
    ),
) -> None:
    await use_case.delete_account_share_default(expense_account)
