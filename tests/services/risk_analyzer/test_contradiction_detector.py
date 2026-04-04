"""Tests for the Contradiction Detector – CV vs platform DISC profile comparison."""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from app.services.disc_scorer.scorer import DISCScores
from app.services.risk_analyzer.contradiction_detector import (
    classify_contradiction,
    compute_contradiction_score,
    compute_disc_distance,
)

# ---- helpers -----------------------------------------------------------------

NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)


def _scores(
    d: float = 50.0,
    i: float = 50.0,
    s: float = 50.0,
    c: float = 50.0,
) -> DISCScores:
    """Build a DISCScores instance with sensible defaults."""
    return DISCScores(
        d=d,
        i=i,
        s=s,
        c=c,
        confidence=0.8,
        dominant="D",
        secondary=None,
        signal_count=10,
        computed_at=NOW,
    )


# ===========================================================================
# compute_disc_distance
# ===========================================================================


class TestComputeDiscDistance:
    """Euclidean distance between two DISC vectors, normalized 0-1."""

    def test_identical_profiles_return_zero(self) -> None:
        a = _scores(d=60, i=40, s=70, c=30)
        b = _scores(d=60, i=40, s=70, c=30)
        assert compute_disc_distance(a, b) == 0.0

    def test_maximally_different_profiles_return_one(self) -> None:
        a = _scores(d=0, i=0, s=0, c=0)
        b = _scores(d=100, i=100, s=100, c=100)
        assert compute_disc_distance(a, b) == pytest.approx(1.0, abs=0.001)

    def test_single_dimension_difference(self) -> None:
        a = _scores(d=0, i=50, s=50, c=50)
        b = _scores(d=100, i=50, s=50, c=50)
        # sqrt(100^2) / 200 = 100/200 = 0.5
        assert compute_disc_distance(a, b) == pytest.approx(0.5, abs=0.001)

    def test_symmetry(self) -> None:
        a = _scores(d=80, i=20, s=60, c=40)
        b = _scores(d=30, i=70, s=10, c=90)
        assert compute_disc_distance(a, b) == pytest.approx(
            compute_disc_distance(b, a)
        )

    def test_result_in_unit_range(self) -> None:
        a = _scores(d=10, i=90, s=30, c=70)
        b = _scores(d=80, i=20, s=60, c=40)
        dist = compute_disc_distance(a, b)
        assert 0.0 <= dist <= 1.0

    def test_known_value(self) -> None:
        # d diff=50, i diff=30, s diff=0, c diff=20
        # sqrt(2500 + 900 + 0 + 400) / 200 = sqrt(3800) / 200
        a = _scores(d=70, i=60, s=50, c=40)
        b = _scores(d=20, i=30, s=50, c=20)
        expected = math.sqrt(3800) / 200.0
        assert compute_disc_distance(a, b) == pytest.approx(expected, abs=0.0001)


# ===========================================================================
# Severity tiers
# ===========================================================================


class TestSeverityTiers:
    """Verify severity tier boundaries from spec."""

    def test_consistent_tier(self) -> None:
        # Identical profiles → score 0.0 → consistent
        cv = _scores(d=50, i=50, s=50, c=50)
        plat = _scores(d=50, i=50, s=50, c=50)
        result = compute_contradiction_score(cv, plat)
        assert result["severity_tier"] == "consistent"
        assert result["contradiction_score"] == 0.0

    def test_minor_divergence_tier(self) -> None:
        # Small difference that produces score in (0.15, 0.30]
        # D diff=30 → sqrt(900)/200 = 0.15 — right on boundary
        # D diff=40 → sqrt(1600)/200 = 0.20
        cv = _scores(d=70, i=50, s=50, c=50)
        plat = _scores(d=30, i=50, s=50, c=50)
        result = compute_contradiction_score(cv, plat)
        assert result["severity_tier"] == "minor_divergence"

    def test_significant_contradiction_tier(self) -> None:
        # Needs score in (0.30, 0.50]
        # d diff=50, i diff=30 → sqrt(2500+900)/200 = sqrt(3400)/200 ≈ 0.2915
        # d diff=60, i diff=40 → sqrt(3600+1600)/200 = sqrt(5200)/200 ≈ 0.3606
        cv = _scores(d=80, i=70, s=50, c=50)
        plat = _scores(d=20, i=30, s=50, c=50)
        result = compute_contradiction_score(cv, plat)
        assert result["severity_tier"] == "significant_contradiction"

    def test_high_contradiction_tier(self) -> None:
        # Needs score in (0.50, 0.70]
        # d=80, i=70, s=70, c=60 vs d=10, i=10, s=10, c=10
        # diffs: 70, 60, 60, 50 → sqrt(4900+3600+3600+2500)/200 = sqrt(14600)/200 ≈ 0.604
        cv = _scores(d=80, i=70, s=70, c=60)
        plat = _scores(d=10, i=10, s=10, c=10)
        result = compute_contradiction_score(cv, plat)
        assert result["severity_tier"] == "high_contradiction"

    def test_severe_contradiction_tier(self) -> None:
        # Needs score > 0.70
        # Max distance profiles → 1.0
        cv = _scores(d=0, i=0, s=0, c=0)
        plat = _scores(d=100, i=100, s=100, c=100)
        result = compute_contradiction_score(cv, plat)
        assert result["severity_tier"] == "severe_contradiction"


# ===========================================================================
# compute_contradiction_score — return structure
# ===========================================================================


class TestContradictionScoreStructure:
    """Verify the result dict shape and types."""

    def test_all_keys_present(self) -> None:
        cv = _scores(d=70, i=60, s=50, c=40)
        plat = _scores(d=30, i=40, s=50, c=60)
        result = compute_contradiction_score(cv, plat)
        expected_keys = {
            "contradiction_score",
            "threshold_exceeded",
            "dimension_gaps",
            "flagged_dimensions",
            "contradiction_type",
            "severity_tier",
        }
        assert set(result.keys()) == expected_keys

    def test_contradiction_score_is_float_in_range(self) -> None:
        cv = _scores(d=70, i=60, s=50, c=40)
        plat = _scores(d=30, i=40, s=50, c=60)
        result = compute_contradiction_score(cv, plat)
        assert isinstance(result["contradiction_score"], float)
        assert 0.0 <= result["contradiction_score"] <= 1.0

    def test_threshold_exceeded_is_bool(self) -> None:
        cv = _scores(d=70, i=60, s=50, c=40)
        plat = _scores(d=30, i=40, s=50, c=60)
        result = compute_contradiction_score(cv, plat)
        assert isinstance(result["threshold_exceeded"], bool)

    def test_dimension_gaps_has_all_four_dims(self) -> None:
        cv = _scores(d=70, i=60, s=50, c=40)
        plat = _scores(d=30, i=40, s=50, c=60)
        result = compute_contradiction_score(cv, plat)
        assert set(result["dimension_gaps"].keys()) == {"D", "I", "S", "C"}

    def test_dimension_gaps_are_absolute_values(self) -> None:
        cv = _scores(d=70, i=30, s=50, c=40)
        plat = _scores(d=30, i=70, s=50, c=60)
        result = compute_contradiction_score(cv, plat)
        for dim, gap in result["dimension_gaps"].items():
            assert gap >= 0.0, f"Gap for {dim} should be non-negative"


# ===========================================================================
# Threshold and flagging logic
# ===========================================================================


class TestThresholdAndFlagging:
    """Test threshold_exceeded and flagged_dimensions logic."""

    def test_threshold_not_exceeded_when_aligned(self) -> None:
        cv = _scores(d=50, i=50, s=50, c=50)
        plat = _scores(d=50, i=50, s=50, c=50)
        result = compute_contradiction_score(cv, plat)
        assert result["threshold_exceeded"] is False
        assert result["flagged_dimensions"] == {}

    def test_threshold_exceeded_above_030(self) -> None:
        # score ~ 0.36 (from significant tier test)
        cv = _scores(d=80, i=70, s=50, c=50)
        plat = _scores(d=20, i=30, s=50, c=50)
        result = compute_contradiction_score(cv, plat)
        assert result["threshold_exceeded"] is True

    def test_flagged_dimensions_only_include_gaps_above_25(self) -> None:
        # D gap = 40 (flagged), I gap = 20 (not flagged), S = 0, C = 10
        cv = _scores(d=70, i=60, s=50, c=50)
        plat = _scores(d=30, i=40, s=50, c=40)
        result = compute_contradiction_score(cv, plat)
        assert "D" in result["flagged_dimensions"]
        assert "I" not in result["flagged_dimensions"]
        assert "S" not in result["flagged_dimensions"]
        assert result["flagged_dimensions"]["D"] == 40.0

    def test_no_flagged_dimensions_when_all_gaps_small(self) -> None:
        cv = _scores(d=50, i=50, s=50, c=50)
        plat = _scores(d=40, i=40, s=40, c=40)
        result = compute_contradiction_score(cv, plat)
        assert result["flagged_dimensions"] == {}

    def test_flagged_dimensions_gap_value_is_correct(self) -> None:
        # C gap = 30 points
        cv = _scores(d=50, i=50, s=50, c=80)
        plat = _scores(d=50, i=50, s=50, c=50)
        result = compute_contradiction_score(cv, plat)
        assert "C" in result["flagged_dimensions"]
        assert result["flagged_dimensions"]["C"] == 30.0


# ===========================================================================
# classify_contradiction
# ===========================================================================


class TestClassifyContradiction:
    """Test all 6 contradiction types."""

    def test_none_when_no_flagged(self) -> None:
        cv = _scores(d=50, i=50, s=50, c=50)
        plat = _scores(d=50, i=50, s=50, c=50)
        result = classify_contradiction(cv, plat, {})
        assert result == "none"

    def test_stated_dominance_not_observed(self) -> None:
        # High D on CV (≥ 70), low D on platform (≤ 40)
        cv = _scores(d=80, i=50, s=50, c=50)
        plat = _scores(d=30, i=50, s=50, c=50)
        flagged = {"D": 50.0}
        result = classify_contradiction(cv, plat, flagged)
        assert result == "stated_dominance_not_observed"

    def test_stability_recovery_pattern(self) -> None:
        # Low S on CV (≤ 40), high S on platform (≥ 70)
        cv = _scores(d=50, i=50, s=30, c=50)
        plat = _scores(d=50, i=50, s=80, c=50)
        flagged = {"S": 50.0}
        result = classify_contradiction(cv, plat, flagged)
        assert result == "stability_recovery_pattern"

    def test_conscientiousness_performance_gap(self) -> None:
        # High C on CV (≥ 70), low C on platform (≤ 40)
        cv = _scores(d=50, i=50, s=50, c=85)
        plat = _scores(d=50, i=50, s=50, c=30)
        flagged = {"C": 55.0}
        result = classify_contradiction(cv, plat, flagged)
        assert result == "conscientiousness_performance_gap"

    def test_emerging_interpersonal_style(self) -> None:
        # High I on platform (≥ 70), low I on CV (≤ 40)
        cv = _scores(d=50, i=30, s=50, c=50)
        plat = _scores(d=50, i=80, s=50, c=50)
        flagged = {"I": 50.0}
        result = classify_contradiction(cv, plat, flagged)
        assert result == "emerging_interpersonal_style"

    def test_multi_dimension_divergence_fallback(self) -> None:
        # Multiple flagged dimensions, no single pattern match.
        # D not high enough on CV to trigger stated_dominance (< 70),
        # S not low enough on CV to trigger stability_recovery,
        # C not high enough on CV, I not high enough on platform.
        cv = _scores(d=60, i=60, s=60, c=60)
        plat = _scores(d=20, i=20, s=20, c=20)
        flagged = {"D": 40.0, "I": 40.0, "S": 40.0, "C": 40.0}
        result = classify_contradiction(cv, plat, flagged)
        assert result == "multi_dimension_divergence"

    def test_priority_stated_dominance_over_others(self) -> None:
        # D pattern matches AND other patterns could match —
        # stated_dominance should win if checked first
        cv = _scores(d=80, i=30, s=30, c=50)
        plat = _scores(d=30, i=80, s=80, c=50)
        flagged = {"D": 50.0, "I": 50.0, "S": 50.0}
        result = classify_contradiction(cv, plat, flagged)
        assert result == "stated_dominance_not_observed"


# ===========================================================================
# Integration: compute_contradiction_score calls classify_contradiction
# ===========================================================================


class TestIntegration:
    """Verify compute_contradiction_score integrates classification."""

    def test_contradiction_type_is_populated(self) -> None:
        cv = _scores(d=80, i=50, s=50, c=50)
        plat = _scores(d=30, i=50, s=50, c=50)
        result = compute_contradiction_score(cv, plat)
        assert result["contradiction_type"] == "stated_dominance_not_observed"

    def test_identical_profiles_yield_none_type(self) -> None:
        cv = _scores(d=50, i=50, s=50, c=50)
        plat = _scores(d=50, i=50, s=50, c=50)
        result = compute_contradiction_score(cv, plat)
        assert result["contradiction_type"] == "none"

    def test_dimension_gaps_match_expected_values(self) -> None:
        cv = _scores(d=80, i=60, s=40, c=20)
        plat = _scores(d=30, i=50, s=70, c=80)
        result = compute_contradiction_score(cv, plat)
        assert result["dimension_gaps"]["D"] == 50.0
        assert result["dimension_gaps"]["I"] == 10.0
        assert result["dimension_gaps"]["S"] == 30.0
        assert result["dimension_gaps"]["C"] == 60.0

    def test_severe_score_has_correct_fields(self) -> None:
        cv = _scores(d=0, i=0, s=0, c=0)
        plat = _scores(d=100, i=100, s=100, c=100)
        result = compute_contradiction_score(cv, plat)
        assert result["contradiction_score"] == pytest.approx(1.0, abs=0.001)
        assert result["threshold_exceeded"] is True
        assert result["severity_tier"] == "severe_contradiction"
        # All dimensions should be flagged (gap=100 each)
        assert len(result["flagged_dimensions"]) == 4
