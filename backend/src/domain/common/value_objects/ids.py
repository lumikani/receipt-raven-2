"""Strongly-typed entity identifiers."""

from dataclasses import dataclass

from ..entity import EntityId


@dataclass(frozen=True)
class ReceiptId(EntityId):
    """Strongly-typed receipt identifier."""

    value: int


@dataclass(frozen=True)
class ReceiptItemId(EntityId):
    """Strongly-typed receipt line item identifier."""

    value: int


@dataclass(frozen=True)
class ReceiptJobId(EntityId):
    """Strongly-typed identifier of a job that analyses an uploaded receipt document."""

    value: int


@dataclass(frozen=True)
class ClassificationRuleId(EntityId):
    """Strongly-typed classification rule identifier."""

    value: int


@dataclass(frozen=True)
class AccountShareDefaultId(EntityId):
    """Strongly-typed account share default identifier."""

    value: int
