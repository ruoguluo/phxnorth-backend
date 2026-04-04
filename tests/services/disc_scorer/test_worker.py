"""Tests for the DISC Scorer Worker orchestrator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.disc_scorer.scorer import WeightedSignal
from app.services.disc_scorer.worker import (
    PRIMARY_WINDOW,
    compute_user_disc_profile,
)

# ---- helpers -----------------------------------------------------------------

NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)


def _signal(
    signal_type: str = "brief_direct_messages",
    confidence: float = 0.8,
    days_ago: int = 0,
    source: str = "platform",
) -> WeightedSignal:
    """Build a WeightedSignal at a given age relative to NOW."""
    return WeightedSignal(
        signal_type=signal_type,
        confidence=confidence,
        timestamp=NOW - timedelta(days=days_ago),
        source=source,
    )


def _career_analytics() -> dict:
    """Return sample career analytics."""
    return {
        "career_volatility_score": 0.5,
        "avg_tenure_months": 24.0,
        "cross_industry_transitions": 2,
        "has_founder_experience": False,
        "transition_frequency": 0.3,
    }


def _behavioral_metrics() -> dict:
    """Return sample behavioral metrics."""
    return {
        "brief_direct_message_rate": 0.6,
        "warm_rapport_rate": 0.3,
        "mentorship_dropout_rate": 0.1,
        "contradiction_score": 0.2,
        "response_latency_cv": 0.15,
        "engagement_variability": 0.1,
    }


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------


class TestReturnStructure:
    """Verify the result dict has all required keys and correct types."""

    @pytest.mark.asyncio
    async def test_all_keys_present(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(signals)
        expected_keys = {
            "profiles",
            "shift",
            "preferences",
            "signal_count",
            "dominant",
            "secondary",
            "confidence",
            "success",
            "error",
        }
        assert set(result.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_profiles_contains_three_windows(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(signals)
        assert set(result["profiles"].keys()) == {"30d", "90d", "lifetime"}

    @pytest.mark.asyncio
    async def test_profiles_are_dicts_with_disc_keys(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(signals)
        for label, profile in result["profiles"].items():
            assert isinstance(profile, dict), f"{label} is not a dict"
            for dim in ("d", "i", "s", "c"):
                assert dim in profile, f"{dim} missing from {label} profile"

    @pytest.mark.asyncio
    async def test_success_is_true_on_valid_input(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(signals)
        assert result["success"] is True
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_dominant_is_valid_disc_dimension(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(signals)
        assert result["dominant"] in {"D", "I", "S", "C"}

    @pytest.mark.asyncio
    async def test_confidence_in_range(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(signals)
        assert 0.0 <= result["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# Empty / no signals
# ---------------------------------------------------------------------------


class TestEmptyInput:
    """Verify behaviour when no signals are provided."""

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty_result(self) -> None:
        result = await compute_user_disc_profile([])
        assert result["success"] is True
        assert result["error"] is None
        assert result["signal_count"] == 0
        assert result["dominant"] is None
        assert result["secondary"] is None
        assert result["confidence"] == 0.0
        assert result["profiles"] == {}
        assert result["shift"] == {}
        assert result["preferences"] == {}


# ---------------------------------------------------------------------------
# Primary window usage
# ---------------------------------------------------------------------------


class TestPrimaryWindow:
    """Verify the 90d window is used as the primary profile."""

    @pytest.mark.asyncio
    async def test_primary_window_is_90d(self) -> None:
        assert PRIMARY_WINDOW == "90d"

    @pytest.mark.asyncio
    async def test_dominant_comes_from_90d(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(signals)
        # Dominant should match the 90d profile's dominant
        assert result["dominant"] == result["profiles"]["90d"]["dominant"]

    @pytest.mark.asyncio
    async def test_confidence_comes_from_90d(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(signals)
        assert result["confidence"] == result["profiles"]["90d"]["confidence"]

    @pytest.mark.asyncio
    async def test_signal_count_comes_from_90d(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(signals)
        assert result["signal_count"] == result["profiles"]["90d"]["signal_count"]


# ---------------------------------------------------------------------------
# Shift detection integration
# ---------------------------------------------------------------------------


class TestShiftDetection:
    """Verify shift detection is correctly wired."""

    @pytest.mark.asyncio
    async def test_shift_result_has_expected_keys(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(signals)
        shift = result["shift"]
        expected_keys = {
            "shift_detected",
            "magnitude",
            "shift_type",
            "shifted_dimensions",
            "interpretation",
        }
        assert set(shift.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_identical_signals_produce_stable_shift(self) -> None:
        # Signals all in the same window => 30d and 90d are identical => stable
        signals = [_signal(days_ago=i) for i in range(5)]
        result = await compute_user_disc_profile(signals)
        assert result["shift"]["shift_type"] == "stable"
        assert result["shift"]["shift_detected"] is False

    @pytest.mark.asyncio
    async def test_divergent_signals_may_detect_shift(self) -> None:
        # D-heavy recent signals + S-heavy older signals
        recent = [
            _signal("brief_direct_messages", confidence=0.9, days_ago=i)
            for i in range(10)
        ]
        older = [
            _signal("long_tenure", confidence=0.9, days_ago=60 + i)
            for i in range(10)
        ]
        signals = recent + older
        result = await compute_user_disc_profile(signals)
        # The shift magnitude should be > 0 (may or may not cross threshold)
        assert result["shift"]["magnitude"] >= 0.0


# ---------------------------------------------------------------------------
# Preference inference integration
# ---------------------------------------------------------------------------


class TestPreferenceInference:
    """Verify preference inference is correctly wired."""

    @pytest.mark.asyncio
    async def test_preferences_computed_when_data_provided(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(
            signals,
            career_analytics=_career_analytics(),
            behavioral_metrics=_behavioral_metrics(),
        )
        prefs = result["preferences"]
        assert "stability_vs_growth" in prefs
        assert "conservative_vs_aggressive_risk" in prefs
        assert "control_vs_collaboration" in prefs
        assert "short_term_vs_long_term" in prefs
        assert "consistency_score" in prefs

    @pytest.mark.asyncio
    async def test_preferences_empty_when_no_supporting_data(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(signals)
        assert result["preferences"] == {}

    @pytest.mark.asyncio
    async def test_preferences_computed_with_career_only(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(
            signals,
            career_analytics=_career_analytics(),
        )
        assert len(result["preferences"]) > 0

    @pytest.mark.asyncio
    async def test_preferences_computed_with_behavioral_only(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(
            signals,
            behavioral_metrics=_behavioral_metrics(),
        )
        assert len(result["preferences"]) > 0

    @pytest.mark.asyncio
    async def test_preference_values_in_range(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(
            signals,
            career_analytics=_career_analytics(),
            behavioral_metrics=_behavioral_metrics(),
        )
        prefs = result["preferences"]
        for key in (
            "stability_vs_growth",
            "conservative_vs_aggressive_risk",
            "control_vs_collaboration",
            "short_term_vs_long_term",
        ):
            assert -1.0 <= prefs[key] <= 1.0, f"{key}={prefs[key]} out of range"
        assert 0.0 <= prefs["consistency_score"] <= 1.0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Worker should never raise; errors are captured in the result."""

    @pytest.mark.asyncio
    async def test_never_raises_on_bad_signal(self) -> None:
        # A signal with unknown type won't crash — scorer logs a warning
        bad = WeightedSignal(
            signal_type="totally_made_up_signal",
            confidence=0.9,
            timestamp=NOW,
            source="platform",
        )
        result = await compute_user_disc_profile([bad])
        assert result["success"] is True


# ---------------------------------------------------------------------------
# User ID parameter
# ---------------------------------------------------------------------------


class TestUserIdParameter:
    """Verify user_id doesn't affect results, just logging."""

    @pytest.mark.asyncio
    async def test_with_user_id(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(signals, user_id="usr_123")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_without_user_id(self) -> None:
        signals = [_signal(days_ago=5)]
        result = await compute_user_disc_profile(signals, user_id=None)
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Multi-age signals
# ---------------------------------------------------------------------------


class TestMultiAgeSignals:
    """Verify mixed-age signals are correctly distributed across windows."""

    @pytest.mark.asyncio
    async def test_signal_counts_across_windows(self) -> None:
        signals = [
            _signal(days_ago=5),    # all windows
            _signal(days_ago=60),   # 90d + lifetime
            _signal(days_ago=200),  # lifetime only
        ]
        result = await compute_user_disc_profile(signals)

        assert result["profiles"]["30d"]["signal_count"] == 1
        assert result["profiles"]["90d"]["signal_count"] == 2
        assert result["profiles"]["lifetime"]["signal_count"] == 3

    @pytest.mark.asyncio
    async def test_wider_windows_have_higher_or_equal_confidence(self) -> None:
        signals = [
            _signal(days_ago=5),
            _signal(days_ago=60),
            _signal(days_ago=200),
        ]
        result = await compute_user_disc_profile(signals)

        c30 = result["profiles"]["30d"]["confidence"]
        c90 = result["profiles"]["90d"]["confidence"]
        clt = result["profiles"]["lifetime"]["confidence"]
        assert clt >= c90 >= c30
