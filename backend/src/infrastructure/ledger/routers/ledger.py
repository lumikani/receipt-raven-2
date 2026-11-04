"""API routes for reading the ledger and the account-role configuration."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.application.ledger.queries.get_account_roles_use_case import GetAccountRolesUseCase
from src.application.ledger.queries.list_ledger_accounts_use_case import (
    ListLedgerAccountsUseCase,
)
from src.application.ledger.queries.list_ledger_payees_use_case import ListLedgerPayeesUseCase
from src.containers import container
from src.domain.ledger.account import AccountType
from src.infrastructure.common.di import inject_use_case
from src.infrastructure.common.schemas import CollectionResponse, ErrorResponse
from src.infrastructure.ledger.schemas import (
    AccountRolesResponse,
    AccountTypeValue,
    LedgerAccount,
)

router = APIRouter(
    prefix="/ledger",
    tags=["ledger"],
    responses={502: {"model": ErrorResponse, "description": "The ledger is not available"}},
)


@router.get("/accounts", response_model=CollectionResponse[LedgerAccount])
async def list_ledger_accounts(
    type: Annotated[
        list[AccountTypeValue] | None, Query(description="Only accounts of these types")
    ] = None,
    use_case: ListLedgerAccountsUseCase = Depends(
        inject_use_case(container.ledger.list_ledger_accounts_use_case)
    ),
) -> CollectionResponse[LedgerAccount]:
    accounts = await use_case.list_accounts([AccountType(value) for value in type or []])
    return CollectionResponse(
        items=[LedgerAccount(name=account.name, type=account.type.value) for account in accounts]
    )


@router.get("/payees", response_model=CollectionResponse[str])
async def list_ledger_payees(
    use_case: ListLedgerPayeesUseCase = Depends(
        inject_use_case(container.ledger.list_ledger_payees_use_case)
    ),
) -> CollectionResponse[str]:
    return CollectionResponse(items=await use_case.list_payees())


@router.get("/account-roles", response_model=AccountRolesResponse)
async def get_account_roles(
    use_case: GetAccountRolesUseCase = Depends(
        inject_use_case(container.ledger.get_account_roles_use_case)
    ),
) -> AccountRolesResponse:
    """The configured account roles; configuration, not the ledger, so no 502."""
    view = await use_case.get_account_roles()
    return AccountRolesResponse(
        personal_cards=list(view.personal_cards),
        shared_card=view.shared_card,
        flatmate_expense_adjustment=view.flatmate_expense_adjustment,
        purchase_for_flatmate=view.purchase_for_flatmate,
        unallocated_account=view.unallocated_account,
    )
