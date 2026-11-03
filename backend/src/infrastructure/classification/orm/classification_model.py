"""SQLAlchemy ORM models for classification rules and account share defaults."""

from datetime import datetime

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base
from src.infrastructure.common.orm_types import UTCDateTime


class ClassificationRuleModel(Base):
    """A row of the `classification_rules` table."""

    __tablename__ = "classification_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The pattern as the user writes it; matching uses the normalized form.
    pattern: Mapped[str] = mapped_column(String(500), nullable=False)
    # Unique per rule: two rules may not normalize to the same product name.
    normalized_pattern: Mapped[str] = mapped_column(
        String(500), nullable=False, unique=True, index=True
    )
    # 0-2; 0 = exact match only.
    max_typos: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    expense_account: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    flatmate_share_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1", index=True)
    # Oldest rule wins fuzzy tie-breaks.
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)


class AccountShareDefaultModel(Base):
    """A row of the `account_share_defaults` table: one per expense account."""

    __tablename__ = "account_share_defaults"

    id: Mapped[int] = mapped_column(primary_key=True)
    expense_account: Mapped[str] = mapped_column(
        String(500), nullable=False, unique=True, index=True
    )
    # Default flatmate share (0-100) for the account.
    share: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)
