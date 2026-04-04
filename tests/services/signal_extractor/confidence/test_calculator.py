"""Tests for signal confidence calculator."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.services.signal_extractor.confidence.calculator import (
    CONTRIBUTION_THRESHOLD,
    DEFAULT_DECAY_RATE,
    MAX_DIMENSION_SCORE,
    MIN_SIGNALS_FOR_FULL_CONFIDENCE,
    apply_temporal_decay,
    calculate_signal_confidence,
)

# ---- helpers -----------------------------------------------------------------

NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)


def _sig(
    dimension: str,
    weight: float,
    days_ago: float = 0.0,
) -> dict:
    """Build a signal dict *days_ago* days before NOW."""
    ts = NOW - timedelta(days=days_ago)
    return {
        "dimension": dimension,
        "weight": weight,
        "timestamp": ts.isoformat(),
    }


# ---------------------------------------------------------------------------
# apply_temporal_decay
# ---------------------------------------------------------------------------


class TestApplyTemporalDecay:
    """Unit tests for the exponential decay function."""

    def test_zero_days_no_decay(self) -> None:
        assert apply_temporal_decay(1.0, 0.0) == 1.0

    def test_positive_days_reduces_weight(self) -> None:
        result = apply_temporal_decay(1.0, 30.0)
        expected = math.exp(-DEFAULT_DECAY_RATE * 30)
        assert result == pytest.approx(expected)
        assert result < 1.0

    def test_negative_days_clamped_to_zero(self) -> None:
        """Future signals should not be amplified."""
        assert apply_temporal_decay(1.0, -5.0) == 1.0

    def test_negative_weight_preserved(self) -> None:
        result = apply_temporal_decay(-0.5, 10.0)
        assert result < 0
        assert result == pytest.approx(-0.5 * math.exp(-DEFAULT_DECAY_RATE * 10))

    def test_custom_decay_rate(self) -> None:
        result = apply_temporal_decay(1.0, 10.0, decay_rate=0.1)
        assert result == pytest.approx(math.exp(-0.1 * 10))

    def test_very_old_signal_nearly_zero(self) -> None:
        result = apply_temporal_decay(1.0, 1000.0)
        assert result < 0.001

    def test_zero_weight_stays_zero(self) -> None:
        assert apply_temporal_decay(0.0, 10.0) == 0.0

    def test_default_decay_70pct_at_30_days(self) -> None:
        """λ = 0.015 should give roughly 64% at 30 days (e^-0.45)."""
        result = apply_temporal_decay(1.0, 30.0)
        assert 0.60 < result < 0.70


# ---------------------------------------------------------------------------
# calculate_signal_confidence – empty / degenerate inputs
# ---------------------------------------------------------------------------


class TestEmptyInputs:
    """Edge cases with no or invalid signals."""

    def test_empty_signal_list(self) -> None:
        result = calculate_signal_confidence([], now=NOW)
        assert result["signal_count"] == 0
        assert result["contributing_signals"] == 0
        assert result["overall_confidence"] == 0.0
        for score in result["dimension_scores"].values():
            assert score == 0.0

    def test_signals_with_invalid_dimension(self) -> None:
        signals = [{"dimension": "X", "weight": 0.5, "timestamp": NOW.isoformat()}]
        result = calculate_signal_confidence(signals, now=NOW)
        assert result["signal_count"] == 0

    def test_signals_with_missing_weight(self) -> None:
        signals = [{"dimension": "D", "timestamp": NOW.isoformat()}]
        result = calculate_signal_confidence(signals, now=NOW)
        assert result["signal_count"] == 0

    def test_signals_with_missing_timestamp(self) -> None:
        signals = [{"dimension": "D", "weight": 0.5}]
        result = calculate_signal_confidence(signals, now=NOW)
        assert result["signal_count"] == 0

    def test_signals_with_bad_timestamp_string(self) -> None:
        signals = [{"dimension": "D", "weight": 0.5, "timestamp": "not-a-date"}]
        result = calculate_signal_confidence(signals, now=NOW)
        assert result["signal_count"] == 0


# ---------------------------------------------------------------------------
# calculate_signal_confidence – single signal
# ---------------------------------------------------------------------------


class TestSingleSignal:
    """Confidence with one signal."""

    def test_single_recent_signal(self) -> None:
        signals = [_sig("D", 0.6, days_ago=0)]
        result = calculate_signal_confidence(signals, now=NOW)

        assert result["signal_count"] == 1
        assert result["contributing_signals"] == 1
        assert result["dimension_scores"]["D"] > 0
        # Other dimensions should be zero
        assert result["dimension_scores"]["I"] == 0.0
        assert result["dimension_scores"]["S"] == 0.0
        assert result["dimension_scores"]["C"] == 0.0

    def test_single_old_signal_has_lower_confidence(self) -> None:
        recent = calculate_signal_confidence([_sig("D", 0.6, 0)], now=NOW)
        old = calculate_signal_confidence([_sig("D", 0.6, 25)], now=NOW)
        assert recent["dimension_scores"]["D"] > old["dimension_scores"]["D"]

    def test_signal_outside_window_ignored(self) -> None:
        signals = [_sig("D", 0.6, days_ago=35)]
        result = calculate_signal_confidence(signals, window_days=30, now=NOW)
        assert result["signal_count"] == 0

    def test_signal_at_window_boundary_included(self) -> None:
        signals = [_sig("D", 0.6, days_ago=30)]
        result = calculate_signal_confidence(signals, window_days=30, now=NOW)
        assert result["signal_count"] == 1


# ---------------------------------------------------------------------------
# calculate_signal_confidence – aggregation
# ---------------------------------------------------------------------------


class TestAggregation:
    """Multiple signals for the same or different dimensions."""

    def test_same_dimension_signals_aggregate(self) -> None:
        signals = [
            _sig("D", 0.5, 0),
            _sig("D", 0.5, 0),
        ]
        one_sig = calculate_signal_confidence([_sig("D", 0.5, 0)], now=NOW)
        two_sig = calculate_signal_confidence(signals, now=NOW)
        assert two_sig["dimension_scores"]["D"] > one_sig["dimension_scores"]["D"]

    def test_different_dimensions_independent(self) -> None:
        signals = [
            _sig("D", 0.6, 0),
            _sig("I", 0.6, 0),
        ]
        result = calculate_signal_confidence(signals, now=NOW)
        assert result["dimension_scores"]["D"] > 0
        assert result["dimension_scores"]["I"] > 0
        assert result["dimension_scores"]["S"] == 0.0
        assert result["dimension_scores"]["C"] == 0.0

    def test_many_signals_increase_overall_confidence(self) -> None:
        few = calculate_signal_confidence(
            [_sig("D", 0.4, 0), _sig("I", 0.4, 0)],
            now=NOW,
        )
        many = calculate_signal_confidence(
            [
                _sig("D", 0.4, 0),
                _sig("I", 0.4, 0),
                _sig("S", 0.4, 0),
                _sig("C", 0.4, 0),
            ],
            now=NOW,
        )
        assert many["overall_confidence"] > few["overall_confidence"]

    def test_negative_weights_reduce_dimension_score(self) -> None:
        positive_only = calculate_signal_confidence(
            [_sig("D", 0.6, 0)], now=NOW,
        )
        with_negative = calculate_signal_confidence(
            [_sig("D", 0.6, 0), _sig("D", -0.4, 0)], now=NOW,
        )
        assert (
            with_negative["dimension_scores"]["D"]
            < positive_only["dimension_scores"]["D"]
        )

    def test_dimension_score_clamped_at_zero(self) -> None:
        """Heavily negative signals should not produce negative confidence."""
        signals = [_sig("D", -2.0, 0)]
        result = calculate_signal_confidence(signals, now=NOW)
        assert result["dimension_scores"]["D"] == 0.0


# ---------------------------------------------------------------------------
# calculate_signal_confidence – temporal decay integration
# ---------------------------------------------------------------------------


class TestTemporalDecayIntegration:
    """Verify that temporal decay affects confidence calculation."""

    def test_recent_beats_old(self) -> None:
        """Same weight, different age → recent signal wins."""
        recent = calculate_signal_confidence([_sig("I", 0.5, 1)], now=NOW)
        old = calculate_signal_confidence([_sig("I", 0.5, 28)], now=NOW)
        assert recent["dimension_scores"]["I"] > old["dimension_scores"]["I"]

    def test_custom_decay_rate(self) -> None:
        fast = calculate_signal_confidence(
            [_sig("S", 0.5, 10)], decay_rate=0.1, now=NOW,
        )
        slow = calculate_signal_confidence(
            [_sig("S", 0.5, 10)], decay_rate=0.001, now=NOW,
        )
        assert slow["dimension_scores"]["S"] > fast["dimension_scores"]["S"]


# ---------------------------------------------------------------------------
# calculate_signal_confidence – contribution threshold
# ---------------------------------------------------------------------------


class TestContributionThreshold:
    """Signals below the threshold should not count as 'contributing'."""

    def test_tiny_weight_not_contributing(self) -> None:
        # A very small weight decayed over time should fall below threshold
        signals = [_sig("D", 0.01, 25)]
        result = calculate_signal_confidence(signals, now=NOW)
        assert result["signal_count"] == 1
        assert result["contributing_signals"] == 0

    def test_decent_weight_is_contributing(self) -> None:
        signals = [_sig("D", 0.5, 0)]
        result = calculate_signal_confidence(signals, now=NOW)
        assert result["contributing_signals"] == 1


# ---------------------------------------------------------------------------
# calculate_signal_confidence – overall confidence penalty
# ---------------------------------------------------------------------------


class TestOverallConfidencePenalty:
    """Low signal count should penalise overall confidence."""

    def test_single_signal_penalised(self) -> None:
        """With fewer signals than MIN_SIGNALS_FOR_FULL_CONFIDENCE, the
        overall score should be reduced."""
        one = calculate_signal_confidence([_sig("D", 1.0, 0)], now=NOW)
        many = calculate_signal_confidence(
            [_sig("D", 1.0, 0)] * MIN_SIGNALS_FOR_FULL_CONFIDENCE,
            now=NOW,
        )
        # one signal → coverage = 1/3 ≈ 0.33 penalty
        # many signals → coverage = 1.0, no penalty
        # Dimension scores are the same, but overall differs
        assert one["overall_confidence"] < many["overall_confidence"]


# ---------------------------------------------------------------------------
# calculate_signal_confidence – output structure
# ---------------------------------------------------------------------------


class TestOutputStructure:
    """Verify the shape of the returned dict."""

    def test_all_keys_present(self) -> None:
        result = calculate_signal_confidence([], now=NOW)
        assert "dimension_scores" in result
        assert "overall_confidence" in result
        assert "signal_count" in result
        assert "contributing_signals" in result

    def test_dimension_scores_has_all_dimensions(self) -> None:
        result = calculate_signal_confidence([], now=NOW)
        for dim in ("D", "I", "S", "C"):
            assert dim in result["dimension_scores"]

    def test_scores_are_bounded(self) -> None:
        """All scores should be within [0, 1]."""
        signals = [_sig(d, 5.0, 0) for d in "DISC"]
        result = calculate_signal_confidence(signals, now=NOW)
        for score in result["dimension_scores"].values():
            assert 0.0 <= score <= 1.0
        assert 0.0 <= result["overall_confidence"] <= 1.0

    def test_overall_confidence_is_float(self) -> None:
        result = calculate_signal_confidence([], now=NOW)
        assert isinstance(result["overall_confidence"], float)

    def test_signal_count_is_int(self) -> None:
        result = calculate_signal_confidence([], now=NOW)
        assert isinstance(result["signal_count"], int)

    def test_contributing_signals_is_int(self) -> None:
        result = calculate_signal_confidence([], now=NOW)
        assert isinstance(result["contributing_signals"], int)


# ---------------------------------------------------------------------------
# calculate_signal_confidence – datetime object timestamps
# ---------------------------------------------------------------------------


class TestDatetimeTimestamps:
    """Signals can carry datetime objects instead of ISO strings."""

    def test_datetime_object_accepted(self) -> None:
        sig = {
            "dimension": "C",
            "weight": 0.5,
            "timestamp": NOW - timedelta(days=2),
        }
        result = calculate_signal_confidence([sig], now=NOW)
        assert result["signal_count"] == 1

    def test_naive_datetime_treated_as_utc(self) -> None:
        naive = datetime(2026, 4, 1, 11, 0, 0)  # no tzinfo
        sig = {"dimension": "C", "weight": 0.5, "timestamp": naive}
        result = calculate_signal_confidence([sig], now=NOW)
        assert result["signal_count"] == 1
