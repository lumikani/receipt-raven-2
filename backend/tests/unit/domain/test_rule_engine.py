"""Unit tests for the classification rule engine: normalization and matching."""

from datetime import UTC, datetime, timedelta

import pytest

from src.domain.classification.entities.classification_rule import ClassificationRule
from src.domain.classification.services.rule_engine import classify_item, normalize_name
from src.domain.common.exceptions import ValidationError
from src.domain.common.value_objects import ClassificationRuleId

UNALLOCATED = "expenses:unallocated"


def rule(
    pattern: str,
    account: str = "expenses:groceries",
    *,
    max_typos: int = 1,
    share_override: float | None = None,
    enabled: bool = True,
    rule_id: int = 1,
    created_at: datetime | None = None,
) -> ClassificationRule:
    return ClassificationRule.create_with_id(
        id=ClassificationRuleId(rule_id),
        pattern=pattern,
        max_typos=max_typos,
        expense_account=account,
        flatmate_share_override=share_override,
        enabled=enabled,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestNormalizeName:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Banaani", "banaani"),
            ("Banaani 2 kpl 3,99 € 7,98 €", "banaani"),
            ("Maito 1 l 1,29 €", "maito 1 l"),
            ("Leipä 400 g", "leipä 400 g"),
            ("Leipä 400g", "leipä 400g"),
            ("Oliiviöljy 0,5 l 4,99 €", "oliiviöljy 0 5 l"),
            ("Kurkku 0,412 kg 2,39 €/kg 0,99 €", "kurkku 0 412 kg"),
            ("Tavaratalo, (Helsinki)!", "tavaratalo helsinki"),
            ("  Kahvi   Pirkka   500g  ", "kahvi pirkka 500g"),
        ],
    )
    def test_normalization(self, raw: str, expected: str) -> None:
        assert normalize_name(raw) == expected

    def test_umlauts_stay_distinct(self) -> None:
        assert normalize_name("Mäyräkoira") != normalize_name("Mayrakoira")
        assert normalize_name("Öljyt") == "öljyt"


class TestMatching:
    def test_exact_match_beats_fuzzy(self) -> None:
        rules = [
            rule("banaan", max_typos=2, rule_id=1),  # fuzzy: distance 1 from "banaani"
            rule("banaani", max_typos=2, rule_id=2),  # exact for "banaani"
        ]
        result = classify_item("Banaani", rules, {"expenses:groceries": 0.0}, UNALLOCATED)
        assert result.matched_rule_id == ClassificationRuleId(2)
        assert not result.flagged

    def test_fuzzy_match_within_max_typos(self) -> None:
        rules = [rule("banaani", max_typos=1)]
        result = classify_item("Banaami", rules, {}, UNALLOCATED)  # one dropped char
        assert result.matched_rule_id == ClassificationRuleId(1)
        assert result.expense_account == "expenses:groceries"

    def test_fuzzy_respects_max_typos_zero_as_exact_only(self) -> None:
        rules = [rule("banaani", max_typos=0)]
        result = classify_item("Banaami", rules, {}, UNALLOCATED)
        assert result.matched_rule_id is None
        assert result.expense_account == UNALLOCATED
        assert result.flagged

    def test_beyond_max_typos_does_not_match(self) -> None:
        rules = [rule("banaani", max_typos=1)]
        result = classify_item("Banaanxyz", rules, {}, UNALLOCATED)
        assert result.matched_rule_id is None

    def test_disabled_rules_never_match(self) -> None:
        rules = [rule("banaani", enabled=False)]
        result = classify_item("Banaani", rules, {}, UNALLOCATED)
        assert result.matched_rule_id is None
        assert result.flagged

    def test_quantity_and_price_tokens_are_stripped_before_matching(self) -> None:
        rules = [rule("banaani", max_typos=0)]
        result = classify_item("Banaani 2 kpl 3,99 € 7,98 €", rules, {}, UNALLOCATED)
        assert result.matched_rule_id == ClassificationRuleId(1)

    def test_fuzzy_prefers_smallest_distance(self) -> None:
        rules = [
            rule("banaani", max_typos=2, rule_id=1),  # distance 1 from "banaanx"
            rule("banaane", max_typos=2, rule_id=2),  # distance 2 from "banaanx"
        ]
        result = classify_item("banaanx", rules, {}, UNALLOCATED)
        assert result.matched_rule_id == ClassificationRuleId(1)

    def test_fuzzy_tie_breaks_by_longest_pattern(self) -> None:
        rules = [
            rule("bana", max_typos=2, rule_id=1, created_at=datetime(2026, 1, 1, tzinfo=UTC)),
            rule("banaanit", max_typos=2, rule_id=2, created_at=datetime(2026, 1, 2, tzinfo=UTC)),
        ]
        # item "banaan" — distance 2 to "bana", distance 2 to "banaanit" → longest wins
        result = classify_item("banaan", rules, {}, UNALLOCATED)
        assert result.matched_rule_id == ClassificationRuleId(2)

    def test_fuzzy_tie_breaks_by_oldest_rule(self) -> None:
        older = datetime(2026, 1, 1, tzinfo=UTC)
        newer = older + timedelta(days=1)
        rules = [
            rule("banaani", rule_id=1, created_at=newer),
            rule("banaani", account="expenses:clothes", rule_id=2, created_at=older),
        ]
        result = classify_item("banaani", rules, {}, UNALLOCATED)
        assert result.matched_rule_id == ClassificationRuleId(2)
        assert result.expense_account == "expenses:clothes"

    def test_unmatched_lands_on_unallocated_and_is_flagged(self) -> None:
        result = classify_item("Höylä", [rule("banaani")], {}, UNALLOCATED)
        assert result.expense_account == UNALLOCATED
        assert result.matched_rule_id is None
        assert result.flatmate_share == 0.0
        assert result.flagged

    def test_empty_name_never_matches(self) -> None:
        result = classify_item("2 kpl 3,99 €", [rule("banaani", max_typos=2)], {}, UNALLOCATED)
        assert result.matched_rule_id is None
        assert result.flagged


class TestShareResolution:
    def test_rule_share_override_beats_account_default(self) -> None:
        rules = [rule("banaani", share_override=100.0)]
        result = classify_item("banaani", rules, {"expenses:groceries": 25.0}, UNALLOCATED)
        assert result.flatmate_share == 100.0
        assert not result.flagged

    def test_account_share_default_applies_without_override(self) -> None:
        rules = [rule("banaani")]
        result = classify_item("banaani", rules, {"expenses:groceries": 25.0}, UNALLOCATED)
        assert result.flatmate_share == 25.0
        assert not result.flagged

    def test_missing_share_default_means_zero_percent_and_a_flag(self) -> None:
        rules = [rule("banaani")]
        result = classify_item("banaani", rules, {}, UNALLOCATED)
        assert result.flatmate_share == 0.0
        assert result.flagged

    def test_unmatched_uses_the_unallocated_accounts_share_default(self) -> None:
        result = classify_item("höylä", [], {UNALLOCATED: 50.0}, UNALLOCATED)
        assert result.flatmate_share == 50.0
        assert result.flagged  # still flagged: no rule matched


class TestFallbackAccount:
    """No rule matched: the analyzer's own account survives (cloud providers)."""

    def test_unmatched_keeps_the_fallback_account_with_its_share_default(self) -> None:
        result = classify_item(
            "Höylä",
            [rule("banaani")],
            {"Expenses:Clothes": 25.0},
            UNALLOCATED,
            fallback_account="Expenses:Clothes",
        )
        assert result.expense_account == "Expenses:Clothes"
        assert result.flatmate_share == 25.0
        assert result.matched_rule_id is None
        assert not result.flagged

    def test_unmatched_fallback_without_share_default_is_zero_and_flagged(self) -> None:
        result = classify_item("Höylä", [], {}, UNALLOCATED, fallback_account="Expenses:Clothes")
        assert result.expense_account == "Expenses:Clothes"
        assert result.flatmate_share == 0.0
        assert result.matched_rule_id is None
        assert result.flagged

    def test_no_fallback_falls_through_to_unallocated(self) -> None:
        # The local OCR parser emits an empty account: the rule engine alone assigns.
        result = classify_item("Höylä", [], {}, UNALLOCATED, fallback_account=None)
        assert result.expense_account == UNALLOCATED
        assert result.matched_rule_id is None
        assert result.flagged

    def test_a_matching_rule_beats_the_fallback_account(self) -> None:
        rules = [rule("banaani", account="expenses:groceries", share_override=100.0)]
        result = classify_item(
            "Banaani",
            rules,
            {},
            UNALLOCATED,
            fallback_account="Expenses:Clothes",
        )
        assert result.expense_account == "expenses:groceries"
        assert result.flatmate_share == 100.0
        assert result.matched_rule_id == ClassificationRuleId(1)
        assert not result.flagged


class TestRuleInvariants:
    def test_max_typos_out_of_range_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            rule("banaani", max_typos=3)

    def test_share_override_out_of_range_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            rule("banaani", share_override=101.0)

    def test_blank_pattern_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            rule("   ")

    def test_pattern_of_only_punctuation_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            rule("!!!")

    def test_pattern_is_stored_normalized(self) -> None:
        assert rule("  Banaani 2 kpl ").normalized_pattern == "banaani"
