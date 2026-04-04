"""Tests for multi-window DISC scoring."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.disc_scorer.scorer import DISCScores, WeightedSignal
from app.services.disc_scorer.windows import compute_windowed_profiles

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


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------


class TestReturnStructure:
    """Verify the return dict has the correct keys and types."""

    def test_returns_dict_with_three_windows(self) -> None:
        signals = [_signal()]
        result = compute_windowed_profiles(signals, now=NOW)
        assert set(result.keys()) == {"30d", "90d", "lifetime"}

    def test_each_value_is_disc_scores(self) -> None:
        signals = [_signal()]
        result = compute_windowed_profiles(signals, now=NOW)
        for key, scores in result.items():
            assert isinstance(scores, DISCScores), f"{key} is not DISCScores"

    def test_empty_signals_returns_three_windows(self) -> None:
        result = compute_windowed_profiles([], now=NOW)
        assert set(result.keys()) == {"30d", "90d", "lifetime"}


# ---------------------------------------------------------------------------
# Window filtering
# ---------------------------------------------------------------------------


class TestWindowFiltering:
    """Verify signals are correctly filtered by temporal window."""

    def test_recent_signal_appears_in_all_windows(self) -> None:
        """A signal from 5 days ago should appear in 30d, 90d, and lifetime."""
        signals = [_signal(days_ago=5)]
        result = compute_windowed_profiles(signals, now=NOW)

        assert result["30d"].signal_count == 1
        assert result["90d"].signal_count == 1
        assert result["lifetime"].signal_count == 1

    def test_45_day_old_signal_excluded_from_30d(self) -> None:
        """A signal from 45 days ago should NOT appear in 30d."""
        signals = [_signal(days_ago=45)]
        result = compute_windowed_profiles(signals, now=NOW)

        assert result["30d"].signal_count == 0
        assert result["90d"].signal_count == 1
        assert result["lifetime"].signal_count == 1

    def test_120_day_old_signal_only_in_lifetime(self) -> None:
        """A signal from 120 days ago should only appear in lifetime."""
        signals = [_signal(days_ago=120)]
        result = compute_windowed_profiles(signals, now=NOW)

        assert result["30d"].signal_count == 0
        assert result["90d"].signal_count == 0
        assert result["lifetime"].signal_count == 1

    def test_boundary_signal_at_exactly_30_days(self) -> None:
        """A signal at exactly 30 days should be included in the 30d window."""
        signals = [_signal(days_ago=30)]
        result = compute_windowed_profiles(signals, now=NOW)

        assert result["30d"].signal_count == 1

    def test_boundary_signal_at_exactly_90_days(self) -> None:
        """A signal at exactly 90 days should be included in the 90d window."""
        signals = [_signal(days_ago=90)]
        result = compute_windowed_profiles(signals, now=NOW)

        assert result["90d"].signal_count == 1

    def test_mixed_age_signals_filter_correctly(self) -> None:
        """Signals of varying ages should filter into appropriate windows."""
        signals = [
            _signal(days_ago=10),   # all windows
            _signal(days_ago=60),   # 90d + lifetime
            _signal(days_ago=200),  # lifetime only
        ]
        result = compute_windowed_profiles(signals, now=NOW)

        assert result["30d"].signal_count == 1
        assert result["90d"].signal_count == 2
        assert result["lifetime"].signal_count == 3


# ---------------------------------------------------------------------------
# Score consistency
# ---------------------------------------------------------------------------


class TestScoreConsistency:
    """Verify scores are consistent across windows."""

    def test_more_signals_means_higher_or_equal_confidence(self) -> None:
        """Wider windows include more signals, so confidence should be >= narrower."""
        signals = [
            _signal(days_ago=10),
            _signal(days_ago=60),
            _signal(days_ago=200),
        ]
        result = compute_windowed_profiles(signals, now=NOW)

        assert result["lifetime"].confidence >= result["90d"].confidence
        assert result["90d"].confidence >= result["30d"].confidence

    def test_identical_signals_same_window_same_score(self) -> None:
        """If all signals fit in 30d, all three windows should produce identical scores."""
        signals = [_signal(days_ago=5), _signal(days_ago=10)]
        result = compute_windowed_profiles(signals, now=NOW)

        # All signals are within 30d, so all windows see the same signals
        assert result["30d"].d == result["90d"].d == result["lifetime"].d
        assert result["30d"].i == result["90d"].i == result["lifetime"].i
        assert result["30d"].signal_count == result["90d"].signal_count == result["lifetime"].signal_count


# ---------------------------------------------------------------------------
# now parameter
# ---------------------------------------------------------------------------


class TestNowParameter:
    """Verify the now parameter behavior."""

    def test_defaults_to_utc_now_when_none(self) -> None:
        """When now is None, function should still work (uses current time)."""
        signals = [_signal(days_ago=0)]
        # No now= parameter — should not raise
        result = compute_windowed_profiles(signals)
        assert set(result.keys()) == {"30d", "90d", "lifetime"}

    def test_custom_now_shifts_windows(self) -> None:
        """Setting now to a different time should shift what's in each window."""
        signal_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        signals = [
            WeightedSignal(
                signal_type="brief_direct_messages",
                confidence=0.8,
                timestamp=signal_time,
                source="platform",
            )
        ]

        # At Feb 15 (45 days later), the signal is outside 30d but inside 90d
        feb_now = datetime(2026, 2, 15, tzinfo=timezone.utc)
        result = compute_windowed_profiles(signals, now=feb_now)

        assert result["30d"].signal_count == 0
        assert result["90d"].signal_count == 1
        assert result["lifetime"].signal_count == 1
