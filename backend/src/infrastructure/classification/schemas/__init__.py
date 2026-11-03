"""Request and response schemas for the classification API."""

import datetime as dt

from pydantic import BaseModel, Field


class ClassificationRule(BaseModel):
    """A stored classification rule."""

    id: int
    pattern: str = Field(description="The product name pattern as entered")
    normalized_pattern: str = Field(description="The normalized form matching runs on")
    max_typos: int = Field(description="0-2; 0 = exact match only")
    expense_account: str
    flatmate_share_override: float | None = Field(
        None, description="Flatmate share (0-100) beating the account default; null = use default"
    )
    enabled: bool
    created_at: dt.datetime


class ClassificationRuleRequest(BaseModel):
    """Body of the create and update requests."""

    pattern: str = Field(..., min_length=1, max_length=500)
    max_typos: int = Field(1, ge=0, le=2, description="0-2; 0 = exact match only")
    expense_account: str = Field(..., min_length=1, max_length=500)
    flatmate_share_override: float | None = Field(None, ge=0, le=100)
    enabled: bool = True


class SetRuleEnabledRequest(BaseModel):
    """Body of the enable/disable request."""

    enabled: bool


class AccountShareDefault(BaseModel):
    """An expense account's default flatmate share."""

    id: int
    expense_account: str
    share: float = Field(description="Default flatmate share, 0-100")
    created_at: dt.datetime


class AccountShareDefaultRequest(BaseModel):
    """Body of the upsert request."""

    expense_account: str = Field(..., min_length=1, max_length=500)
    share: float = Field(..., ge=0, le=100)


__all__ = [
    "AccountShareDefault",
    "AccountShareDefaultRequest",
    "ClassificationRule",
    "ClassificationRuleRequest",
    "SetRuleEnabledRequest",
]
