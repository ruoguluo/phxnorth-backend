"""Integration tests: Signal Extractor → DISC Scorer full pipeline.

Exercises the complete path from raw behavioral events through signal
extraction, DISC scoring, windowed profiles, shift detection, and
preference inference — using real service functions (no mocks).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from app.services.disc_scorer.preference_inference import infer_preferences
from app.services.disc_scorer.scorer import (
    DISCScores,
    WeightedSignal,
    compute_disc_scores,
)
from app.services.disc_scorer.shift_detector import detect_personality_shift
from app.services.disc_scorer.windows import compute_windowed_profiles
from app.services.disc_scorer.worker import compute_user_disc_profile
from app.services.signal_extractor.worker import process_behavioral_events

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
USER_ID = str(uuid.uuid4())


def _event(
    event_type: str,
    payload: dict | None = None,
    *,
    user_id: str = USER_ID,
    created_at: datetime | None = None,
    **extra: object,
) -> dict[str, Any]:
    """Build a valid raw event dict."""
    return {
        "user_id": user_id,
        "event_type": event_type,
        "payload": payload or {},
        "created_at": (created_at or NOW).isoformat(),
        **extra,
    }


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
    """Sample career analytics for preference inference."""
    return {
        "career_volatility_score": 0.5,
        "avg_tenure_months": 24.0,
        "cross_industry_transitions": 2,
        "has_founder_experience": False,
        "transition_frequency": 0.3,
    }


def _behavioral_metrics() -> dict:
    """Sample behavioral metrics for preference inference."""
    return {
        "brief_direct_message_rate": 0.6,
        "warm_rapport_rate": 0.3,
        "mentorship_dropout_rate": 0.1,
        "contradiction_score": 0.2,
        "response_latency_cv": 0.15,
        "engagement_variability": 0.1,
    }


# ===========================================================================
# Task 4: Events → Signals → DISC Scores (full pipeline)
# ===========================================================================


class TestEventsToSignalsToDiscScores:
    """Feed sample events through signal extractor, then compute DISC scores."""

    @pytest.mark.asyncio
    async def test_full_event_to_disc_pipeline(self) -> None:
        """Events → extract signals → build WeightedSignals → compute DISC scores."""
        events = [
            _event("CLICK"),
            _event("MESSAGE_SENT"),
            _event("TASK_COMPLETED"),
            _event("TASK_STARTED"),
            _event("MENTORSHIP_REQUESTED"),
        ]

        # Step 1: Extract raw signals from behavioral events
        extraction = await process_behavioral_events(events, user_id=USER_ID)
        assert extraction["success"] is True
        assert extraction["signal_count"] > 0

        raw_signals = extraction["signals"]

        # Step 2: Convert extracted signals to WeightedSignal objects
        weighted: list[WeightedSignal] = []
        for sig in raw_signals:
            weighted.append(
                WeightedSignal(
                    signal_type=sig["event_type"],
                    confidence=abs(sig["weight"]),
                    timestamp=datetime.fromisoformat(sig["timestamp"]),
                    source="platform",
                )
            )

        # Step 3: Compute DISC scores
        scores = compute_disc_scores(weighted, now=NOW)

        assert isinstance(scores, DISCScores)
        assert 0.0 <= scores.d <= 100.0
        assert 0.0 <= scores.i <= 100.0
        assert 0.0 <= scores.s <= 100.0
        assert 0.0 <= scores.c <= 100.0
        assert scores.dominant in {"D", "I", "S", "C"}
        assert scores.confidence >= 0.0

    @pytest.mark.asyncio
    async def test_high_d_events_bias_d_dimension(self) -> None:
        """D-heavy events should push the D score above the midpoint."""
        # CLICK contributes D+I, TASK_STARTED contributes D+C, TASK_COMPLETED
        # contributes C+D+S.  Together they give substantial D weight.
        events = [
            _event("CLICK"),
            _event("CLICK"),
            _event("TASK_STARTED"),
            _event("TASK_STARTED"),
            _event("TASK_COMPLETED", {
                "deadline": (NOW + timedelta(hours=2)).isoformat(),
                "completed_at": NOW.isoformat(),
            }),
        ]

        extraction = await process_behavioral_events(events, user_id=USER_ID)
        assert extraction["success"] is True

        weighted = [
            WeightedSignal(
                signal_type=sig["event_type"],
                confidence=abs(sig["weight"]),
                timestamp=datetime.fromisoformat(sig["timestamp"]),
                source="platform",
            )
            for sig in extraction["signals"]
        ]

        scores = compute_disc_scores(weighted, now=NOW)
        # D should be above midpoint (50) given D-heavy events
        assert scores.d >= 50.0

    @pytest.mark.asyncio
    async def test_social_events_bias_i_dimension(self) -> None:
        """I-heavy events should push I score higher."""
        events = [
            _event("MESSAGE_SENT"),
            _event("MESSAGE_SENT"),
            _event("CONNECTION_REQUESTED"),
            _event("CONTENT_SHARED"),
            _event("COMMENT_POSTED"),
        ]

        extraction = await process_behavioral_events(events, user_id=USER_ID)
        assert extraction["success"] is True

        weighted = [
            WeightedSignal(
                signal_type=sig["event_type"],
                confidence=abs(sig["weight"]),
                timestamp=datetime.fromisoformat(sig["timestamp"]),
                source="platform",
            )
            for sig in extraction["signals"]
        ]

        scores = compute_disc_scores(weighted, now=NOW)
        # I should be the highest or at least well above midpoint
        assert scores.i >= 50.0

    @pytest.mark.asyncio
    async def test_full_pipeline_via_worker(self) -> None:
        """Exercise the full pipeline end-to-end through both workers."""
        events = [
            _event("CLICK"),
            _event("MESSAGE_SENT"),
            _event("TASK_COMPLETED"),
            _event("MENTORSHIP_REQUESTED"),
            _event("FORM_SUBMIT"),
        ]

        # Step 1: Signal extraction
        extraction = await process_behavioral_events(events, user_id=USER_ID)
        assert extraction["success"] is True

        # Step 2: Build WeightedSignals from extracted signals
        weighted = [
            WeightedSignal(
                signal_type=sig["event_type"],
                confidence=abs(sig["weight"]),
                timestamp=datetime.fromisoformat(sig["timestamp"]),
                source="platform",
            )
            for sig in extraction["signals"]
        ]

        # Step 3: Compute full DISC profile via worker
        result = await compute_user_disc_profile(
            weighted,
            career_analytics=_career_analytics(),
            behavioral_metrics=_behavioral_metrics(),
            user_id=USER_ID,
        )

        assert result["success"] is True
        assert result["dominant"] in {"D", "I", "S", "C"}
        assert result["confidence"] >= 0.0
        assert "30d" in result["profiles"]
        assert "90d" in result["profiles"]
        assert "lifetime" in result["profiles"]
        assert result["shift"]["shift_type"] in {
            "stable", "situational", "structural", "transitional",
        }


# ===========================================================================
# Windowed Scoring with Aged Signals
# ===========================================================================


class TestWindowedScoringWithAgedSignals:
    """Create signals at different ages, verify windowed scores differ."""

    def test_recent_signals_appear_in_all_windows(self) -> None:
        """A signal from 5 days ago should appear in 30d, 90d, and lifetime."""
        signals = [_signal("brief_direct_messages", days_ago=5)]
        profiles = compute_windowed_profiles(signals, now=NOW)

        assert profiles["30d"].signal_count == 1
        assert profiles["90d"].signal_count == 1
        assert profiles["lifetime"].signal_count == 1

    def test_old_signal_excluded_from_narrow_window(self) -> None:
        """A 60-day-old signal is excluded from 30d but included in 90d/lifetime."""
        signals = [_signal("brief_direct_messages", days_ago=60)]
        profiles = compute_windowed_profiles(signals, now=NOW)

        assert profiles["30d"].signal_count == 0
        assert profiles["90d"].signal_count == 1
        assert profiles["lifetime"].signal_count == 1

    def test_very_old_signal_only_in_lifetime(self) -> None:
        """A 200-day-old signal is only in the lifetime window."""
        signals = [_signal("brief_direct_messages", days_ago=200)]
        profiles = compute_windowed_profiles(signals, now=NOW)

        assert profiles["30d"].signal_count == 0
        assert profiles["90d"].signal_count == 0
        assert profiles["lifetime"].signal_count == 1

    def test_mixed_age_signals_produce_different_profiles(self) -> None:
        """Different temporal distributions should produce different scores."""
        recent = [
            _signal("brief_direct_messages", confidence=0.9, days_ago=i)
            for i in range(5)
        ]
        older = [
            _signal("long_tenure", confidence=0.9, days_ago=60 + i)
            for i in range(5)
        ]
        signals = recent + older

        profiles = compute_windowed_profiles(signals, now=NOW)

        # 30d window only sees D-heavy "brief_direct_messages"
        # 90d window sees both D-heavy and S-heavy signals
        # The profiles should differ
        assert profiles["30d"].signal_count == 5
        assert profiles["90d"].signal_count == 10
        assert profiles["lifetime"].signal_count == 10

        # The 30d D score should differ from lifetime because of signal mix
        # (brief_direct_messages: D=+0.70, long_tenure: D=-0.30)
        assert profiles["30d"].d != profiles["lifetime"].d

    def test_temporal_decay_affects_scores(self) -> None:
        """Same signal type but different ages should produce different scores
        due to temporal decay in compute_disc_scores."""
        recent_signals = [
            _signal("brief_direct_messages", confidence=0.9, days_ago=1),
        ]
        old_signals = [
            _signal("brief_direct_messages", confidence=0.9, days_ago=80),
        ]

        recent_scores = compute_disc_scores(recent_signals, now=NOW)
        old_scores = compute_disc_scores(old_signals, now=NOW)

        # Both produce one recognized signal
        assert recent_scores.signal_count == 1
        assert old_scores.signal_count == 1

        # Recent signal gets higher effective weight → more extreme D score
        # (brief_direct_messages: D=+0.70 pushes D above midpoint)
        # Old signal is decayed → D closer to midpoint (50)
        assert recent_scores.d > old_scores.d


# ===========================================================================
# Shift Detection with Divergent Signals
# ===========================================================================


class TestShiftDetectionWithDivergentSignals:
    """Create signals that should trigger shift detection."""

    def test_identical_signal_distribution_is_stable(self) -> None:
        """Same signals in both windows → no shift detected."""
        signals = [_signal("brief_direct_messages", days_ago=i) for i in range(10)]
        profiles = compute_windowed_profiles(signals, now=NOW)
        shift = detect_personality_shift(profiles)

        assert shift["shift_detected"] is False
        assert shift["shift_type"] == "stable"
        assert shift["magnitude"] < 0.25  # below threshold

    def test_divergent_recent_vs_baseline_detects_shift(self) -> None:
        """D-heavy recent + S-heavy older signals should show a shift."""
        # Recent signals: D-dominant (brief_direct_messages: D=+0.70)
        recent = [
            _signal("brief_direct_messages", confidence=0.95, days_ago=i)
            for i in range(15)
        ]
        # Older signals: S-dominant (long_tenure: S=+0.70)
        older = [
            _signal("long_tenure", confidence=0.95, days_ago=45 + i)
            for i in range(15)
        ]
        signals = recent + older

        profiles = compute_windowed_profiles(signals, now=NOW)
        shift = detect_personality_shift(profiles)

        # 30d window is dominated by D-heavy signals
        # 90d window mixes both → different profile
        assert shift["magnitude"] > 0.0
        # The shifted_dimensions should show D going up or S going down
        shifted = shift["shifted_dimensions"]
        assert isinstance(shifted, dict)
        assert set(shifted.keys()) == {"D", "I", "S", "C"}

    def test_large_divergence_detected_as_transitional_or_situational(self) -> None:
        """Strongly divergent signals should produce a meaningful shift type."""
        # Very strong recent D signal (founder_experience: D=+0.80)
        recent = [
            _signal("founder_experience", confidence=0.95, days_ago=i)
            for i in range(20)
        ]
        # Strong older S signal (high_collaboration_consistency: S=+0.60)
        older = [
            _signal("high_collaboration_consistency", confidence=0.95, days_ago=50 + i)
            for i in range(20)
        ]
        signals = recent + older

        profiles = compute_windowed_profiles(signals, now=NOW)
        shift = detect_personality_shift(profiles)

        # Should detect a shift of some kind
        assert shift["shift_type"] in {"situational", "structural", "transitional"}
        assert shift["shift_detected"] is True

    def test_shift_interpretation_non_empty_on_shift(self) -> None:
        """When a shift is detected, interpretation should describe it."""
        recent = [
            _signal("brief_direct_messages", confidence=0.95, days_ago=i)
            for i in range(20)
        ]
        older = [
            _signal("long_tenure", confidence=0.95, days_ago=50 + i)
            for i in range(20)
        ]
        signals = recent + older

        profiles = compute_windowed_profiles(signals, now=NOW)
        shift = detect_personality_shift(profiles)

        assert isinstance(shift["interpretation"], str)
        assert len(shift["interpretation"]) > 0

    def test_stable_shift_interpretation(self) -> None:
        """Stable profiles get the 'Profile is stable across windows' message."""
        signals = [_signal("brief_direct_messages", days_ago=i) for i in range(5)]
        profiles = compute_windowed_profiles(signals, now=NOW)
        shift = detect_personality_shift(profiles)

        assert shift["shift_type"] == "stable"
        assert "stable" in shift["interpretation"].lower()


# ===========================================================================
# Preference Inference from DISC Scores
# ===========================================================================


class TestPreferenceInferenceFromDiscScores:
    """Compute preferences from DISC scores via the full pipeline."""

    def test_high_d_favors_growth_and_risk(self) -> None:
        """High D score should push toward growth-seeking and risk-aggressive."""
        high_d = DISCScores(
            d=95.0, i=25.0, s=15.0, c=25.0,
            confidence=0.9, dominant="D", secondary=None,
            signal_count=20, computed_at=NOW,
        )
        ca = {
            "career_volatility_score": 0.9,
            "avg_tenure_months": 8.0,
            "cross_industry_transitions": 4,
            "has_founder_experience": True,
            "transition_frequency": 0.7,
        }
        bm = {
            "brief_direct_message_rate": 0.9,
            "warm_rapport_rate": 0.05,
            "mentorship_dropout_rate": 0.4,
            "contradiction_score": 0.1,
            "response_latency_cv": 0.1,
            "engagement_variability": 0.1,
        }

        prefs = infer_preferences(high_d, ca, bm)

        # High D + very volatile career + founder + very low S/C → growth-seeking
        assert prefs.stability_vs_growth > 0.0
        # High D + founder + many cross-industry → risk-aggressive
        assert prefs.conservative_vs_aggressive_risk > 0.0
        # D-dominant profile: control_vs_collaboration is higher (less negative)
        # than a low-D profile would produce — we verify the relative direction
        # in test_high_s_favors_stability_and_conservatism below
        low_d = DISCScores(
            d=20.0, i=70.0, s=80.0, c=60.0,
            confidence=0.9, dominant="S", secondary="I",
            signal_count=20, computed_at=NOW,
        )
        prefs_low_d = infer_preferences(low_d, ca, bm)
        assert prefs.control_vs_collaboration > prefs_low_d.control_vs_collaboration
        # All within valid ranges
        assert -1.0 <= prefs.stability_vs_growth <= 1.0
        assert -1.0 <= prefs.conservative_vs_aggressive_risk <= 1.0
        assert -1.0 <= prefs.control_vs_collaboration <= 1.0
        assert -1.0 <= prefs.short_term_vs_long_term <= 1.0
        assert 0.0 <= prefs.consistency_score <= 1.0

    def test_high_s_favors_stability_and_conservatism(self) -> None:
        """High S score should push toward stability-seeking and conservative."""
        high_s = DISCScores(
            d=30.0, i=40.0, s=85.0, c=60.0,
            confidence=0.9, dominant="S", secondary="C",
            signal_count=20, computed_at=NOW,
        )
        ca = {
            "career_volatility_score": 0.1,
            "avg_tenure_months": 60.0,
            "cross_industry_transitions": 0,
            "has_founder_experience": False,
            "transition_frequency": 0.1,
        }
        bm = {
            "brief_direct_message_rate": 0.2,
            "warm_rapport_rate": 0.7,
            "mentorship_dropout_rate": 0.05,
            "contradiction_score": 0.05,
            "response_latency_cv": 0.05,
            "engagement_variability": 0.05,
        }

        prefs = infer_preferences(high_s, ca, bm)

        # High S + low volatility + long tenure → stability-seeking (negative)
        assert prefs.stability_vs_growth < 0.0
        # High S + no founder + no cross-industry → conservative (negative)
        assert prefs.conservative_vs_aggressive_risk < 0.0
        # Low contradiction + low variability → high consistency
        assert prefs.consistency_score > 0.7

    @pytest.mark.asyncio
    async def test_preferences_via_disc_worker_pipeline(self) -> None:
        """Full pipeline: WeightedSignals → DISC Worker → preferences."""
        # Build signals that favor D
        signals = [
            _signal("brief_direct_messages", confidence=0.9, days_ago=i)
            for i in range(10)
        ]

        result = await compute_user_disc_profile(
            signals,
            career_analytics=_career_analytics(),
            behavioral_metrics=_behavioral_metrics(),
            user_id=USER_ID,
        )

        assert result["success"] is True
        prefs = result["preferences"]
        assert len(prefs) > 0

        # Check all five preference indexes are present
        assert "stability_vs_growth" in prefs
        assert "conservative_vs_aggressive_risk" in prefs
        assert "control_vs_collaboration" in prefs
        assert "short_term_vs_long_term" in prefs
        assert "consistency_score" in prefs

        # Bipolar indexes in range
        for key in (
            "stability_vs_growth",
            "conservative_vs_aggressive_risk",
            "control_vs_collaboration",
            "short_term_vs_long_term",
        ):
            assert -1.0 <= prefs[key] <= 1.0, f"{key}={prefs[key]} out of range"
        assert 0.0 <= prefs["consistency_score"] <= 1.0

    def test_consistency_degrades_with_contradiction(self) -> None:
        """Higher contradiction_score → lower consistency_score."""
        disc = DISCScores(
            d=50.0, i=50.0, s=50.0, c=50.0,
            confidence=0.9, dominant="D", secondary=None,
            signal_count=20, computed_at=NOW,
        )
        ca = _career_analytics()

        low_contradiction_bm = {**_behavioral_metrics(), "contradiction_score": 0.1}
        high_contradiction_bm = {**_behavioral_metrics(), "contradiction_score": 0.8}

        prefs_low = infer_preferences(disc, ca, low_contradiction_bm)
        prefs_high = infer_preferences(disc, ca, high_contradiction_bm)

        assert prefs_low.consistency_score > prefs_high.consistency_score
