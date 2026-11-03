"""The classification rule engine: match a receipt item name to a rule.

Pipeline per item name: normalize (lowercase, punctuation → space, whitespace
collapsed, quantity/price tokens such as `2 kpl` / `3,99 eur` stripped — size
tokens like `0 5l` / `400g` stay, no ä/ö folding) → exact full-string match →
else fuzzy full-string Levenshtein within the rule's `max_typos`.

Precedence: exact beats fuzzy; among fuzzy hits smallest distance, then
longest pattern, then oldest rule. Share resolution on a match: the rule's
share override → the account's share default → 0% plus a flag. No match →
the unallocated account plus a flag, `matched_rule_id = None`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from rapidfuzz.distance import Levenshtein

from src.domain.common.value_object import ValueObject
from src.domain.common.value_objects import ClassificationRuleId

if TYPE_CHECKING:
    from src.domain.classification.entities.classification_rule import ClassificationRule

# Quantity/price tokens stripped from item names only; patterns are stored clean.
# Size tokens (`0 5l`, `400g`) are not matched here and stay part of the name.
_PRICE_TOKEN = re.compile(r"\d+(?:[,.]\d+)?\s*(?:€|eur\b)(?:\s*/\s*[a-z]+)?", re.IGNORECASE)
_QUANTITY_TOKEN = re.compile(r"\d+(?:[,.]\d+)?\s*(?:kpl|pcs|stk)\b", re.IGNORECASE)
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Normalize a product name (or a rule pattern) for matching.

    Lowercase, punctuation → space, whitespace collapsed, quantity/price
    tokens removed. Letters keep their case-folding only: ä and ö stay distinct.
    """
    text = name.lower()
    text = _PRICE_TOKEN.sub(" ", text)
    text = _QUANTITY_TOKEN.sub(" ", text)
    text = _PUNCTUATION.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


@dataclass(frozen=True)
class _FuzzyHit:
    """One fuzzy candidate; ordering is the spec's tie-break."""

    distance: int
    pattern_length: int
    created_at: datetime
    rule_id: int
    rule: ClassificationRule

    @property
    def order_key(self) -> tuple[int, int, datetime, int]:
        """Smallest distance, then longest pattern, then oldest rule."""
        return (self.distance, -self.pattern_length, self.created_at, self.rule_id)


@dataclass(frozen=True)
class ClassificationResult(ValueObject):
    """What the engine stamped onto one receipt item.

    `flagged` marks items needing review: no rule matched, or the matched
    account has no share default (share falls back to 0%).
    """

    expense_account: str
    flatmate_share: float
    matched_rule_id: ClassificationRuleId | None
    flagged: bool


def _result_for_match(
    rule: ClassificationRule, share_defaults: dict[str, float]
) -> ClassificationResult:
    if rule.flatmate_share_override is not None:
        return ClassificationResult(
            expense_account=rule.expense_account,
            flatmate_share=rule.flatmate_share_override,
            matched_rule_id=rule.id,
            flagged=False,
        )
    share = share_defaults.get(rule.expense_account)
    if share is None:
        return ClassificationResult(
            expense_account=rule.expense_account,
            flatmate_share=0.0,
            matched_rule_id=rule.id,
            flagged=True,
        )
    return ClassificationResult(
        expense_account=rule.expense_account,
        flatmate_share=share,
        matched_rule_id=rule.id,
        flagged=False,
    )


def classify_item(
    item_name: str,
    rules: list[ClassificationRule],
    share_defaults: dict[str, float],
    unallocated_account: str,
) -> ClassificationResult:
    """Classify one receipt item name against the enabled rules.

    Args:
        item_name: The product name as the analysis or the user wrote it.
        rules: Every stored rule; disabled ones never match.
        share_defaults: Expense account → default flatmate share (0-100).
        unallocated_account: Account for items no rule matches.
    """
    normalized = normalize_name(item_name)
    enabled = [rule for rule in rules if rule.enabled]
    if normalized:
        exact = [rule for rule in enabled if rule.normalized_pattern == normalized]
        if exact:
            # Normalized patterns are unique; the tie-break only guards duplicates.
            rule = min(exact, key=lambda r: (r.created_at, r.id.value))
            return _result_for_match(rule, share_defaults)
        fuzzy: list[_FuzzyHit] = []
        for rule in enabled:
            if rule.max_typos <= 0:
                continue  # 0 = exact only
            distance = Levenshtein.distance(normalized, rule.normalized_pattern)
            if distance <= rule.max_typos:
                fuzzy.append(
                    _FuzzyHit(
                        distance=distance,
                        pattern_length=len(rule.normalized_pattern),
                        created_at=rule.created_at,
                        rule_id=rule.id.value,
                        rule=rule,
                    )
                )
        if fuzzy:
            rule = min(fuzzy, key=lambda hit: hit.order_key).rule
            return _result_for_match(rule, share_defaults)
    share = share_defaults.get(unallocated_account, 0.0)
    return ClassificationResult(
        expense_account=unallocated_account,
        flatmate_share=share,
        matched_rule_id=None,
        flagged=True,
    )
