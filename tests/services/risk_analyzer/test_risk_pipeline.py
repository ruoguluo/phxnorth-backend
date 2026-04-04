"""Integration tests: Risk Analyzer full pipeline.

Exercises the complete risk analysis path from DISC profiles through
contradiction detection, risk scoring (7 categories), red flag generation,
and the orchestrating worker — using real service functions (no mocks).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from app.services.disc_scorer.preference_inference import PreferenceIndexes
from app.services.disc_scorer.scorer import DISCScores
from app.services.risk_analyzer.contradiction_detector import (
    compute_contradiction_score,
)
from app.services.risk_analyzer.red_flag_engine import generate_red_flags
from app.services.risk_analyzer.risk_predictor import compute_risk_scores
from app.services.risk_analyzer.worker import analyze_user_risk

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
USER_ID = "user-risk-test-001"


def _scores(
    d: float = 50.0,
    i: float = 50.0,
    s: float = 50.0,
    c: float = 50.0,
    *,
    dominant: str = "D",
    secondary: str | None = None,
    confidence: float = 0.8,
) -> DISCScores:
    """Build a DISCScores instance with sensible defaults."""
    return DISCScores(
        d=d,
        i=i,
        s=s,
        c=c,
        confidence=confidence,
        dominant=dominant,
        secondary=secondary,
        signal_count=20,
        computed_at=NOW,
    )


def _neutral_prefs() -> PreferenceIndexes:
    """Build neutral preference indexes."""
    return PreferenceIndexes(
        stability_vs_growth=0.0,
        conservative_vs_aggressive_risk=0.0,
        control_vs_collaboration=0.0,
        short_term_vs_long_term=0.0,
        consistency_score=0.5,
    )


def _risky_career_analytics() -> dict:
    """Career analytics that indicate instability / high risk."""
    return {
        "career_volatility_score": 0.85,
        "avg_tenure_months": 8.0,
        "cross_industry_transitions": 4,
        "has_founder_experience": False,
        "transition_frequency": 0.8,
        "short_tenure_rate": 0.7,
    }


def _stable_career_analytics() -> dict:
    """Career analytics that indicate stability / low risk."""
    return {
        "career_volatility_score": 0.1,
        "avg_tenure_months": 48.0,
        "cross_industry_transitions": 0,
        "has_founder_experience": False,
        "transition_frequency": 0.1,
        "short_tenure_rate": 0.05,
    }


def _risky_behavioral_metrics() -> dict:
    """Behavioral metrics that indicate problems across multiple categories."""
    return {
        "task_completion_rate": 0.3,
        "avg_days_overdue": 8.0,
        "response_latency_cv": 0.9,
        "mentorship_dropout_rate": 0.8,
        "variable_engagement_score": 0.7,
        "collaboration_consistency_score": 0.2,
        "persistent_task_lateness_rate": 0.7,
        "slow_deliberate_response_rate": 0.2,
        "project_initiative_rate": 0.2,
        "shift_magnitude": 0.6,
        "contradiction_score": 0.6,
    }


def _healthy_behavioral_metrics() -> dict:
    """Behavioral metrics indicating good performance."""
    return {
        "task_completion_rate": 0.95,
        "avg_days_overdue": 0.5,
        "response_latency_cv": 0.1,
        "mentorship_dropout_rate": 0.05,
        "variable_engagement_score": 0.1,
        "collaboration_consistency_score": 0.9,
        "persistent_task_lateness_rate": 0.05,
        "slow_deliberate_response_rate": 0.1,
        "project_initiative_rate": 0.8,
        "shift_magnitude": 0.05,
        "contradiction_score": 0.05,
    }


# ===========================================================================
# Task 5: Contradiction Detection — Aligned Profiles
# ===========================================================================


class TestContradictionDetectionAlignedProfiles:
    """Low contradiction when CV matches platform profile."""

    def test_identical_profiles_consistent(self) -> None:
        cv = _scores(d=60, i=50, s=55, c=65)
        plat = _scores(d=60, i=50, s=55, c=65)
        result = compute_contradiction_score(cv, plat)

        assert result["contradiction_score"] == 0.0
        assert result["threshold_exceeded"] is False
        assert result["severity_tier"] == "consistent"
        assert result["contradiction_type"] == "none"
        assert result["flagged_dimensions"] == {}

    def test_nearly_identical_profiles_low_score(self) -> None:
        """Small differences (< 10 pts each dim) → consistent or minor."""
        cv = _scores(d=55, i=48, s=52, c=60)
        plat = _scores(d=50, i=50, s=50, c=55)
        result = compute_contradiction_score(cv, plat)

        assert result["contradiction_score"] < 0.15
        assert result["severity_tier"] == "consistent"
        assert result["threshold_exceeded"] is False

    def test_moderate_alignment_stays_below_threshold(self) -> None:
        """Differences of ~15 pts per dim stay below 0.30 threshold."""
        cv = _scores(d=60, i=55, s=45, c=65)
        plat = _scores(d=50, i=45, s=50, c=55)
        result = compute_contradiction_score(cv, plat)

        # Gaps: D=10, I=10, S=5, C=10 → sqrt(100+100+25+100)/200 ≈ 0.090
        assert result["contradiction_score"] < 0.30
        assert result["threshold_exceeded"] is False
        assert result["flagged_dimensions"] == {}

    def test_aligned_profiles_no_flagged_dimensions(self) -> None:
        """When no dimension gap exceeds 25 pts, nothing is flagged."""
        cv = _scores(d=70, i=60, s=50, c=40)
        plat = _scores(d=55, i=50, s=45, c=35)
        result = compute_contradiction_score(cv, plat)

        for dim, gap in result["dimension_gaps"].items():
            assert gap <= 25.0, f"{dim} gap {gap} should be ≤ 25"
        assert result["flagged_dimensions"] == {}


# ===========================================================================
# Contradiction Detection — Divergent Profiles
# ===========================================================================


class TestContradictionDetectionDivergentProfiles:
    """High contradiction when CV diverges from platform profile."""

    def test_opposite_profiles_severe(self) -> None:
        """Maximally different profiles → severe contradiction."""
        cv = _scores(d=0, i=0, s=0, c=0)
        plat = _scores(d=100, i=100, s=100, c=100)
        result = compute_contradiction_score(cv, plat)

        assert result["contradiction_score"] == pytest.approx(1.0, abs=0.01)
        assert result["threshold_exceeded"] is True
        assert result["severity_tier"] == "severe_contradiction"
        assert len(result["flagged_dimensions"]) == 4

    def test_high_d_cv_low_d_platform(self) -> None:
        """High D on CV, low D on platform → stated_dominance_not_observed."""
        cv = _scores(d=85, i=50, s=50, c=50)
        plat = _scores(d=20, i=50, s=50, c=50)
        result = compute_contradiction_score(cv, plat)

        assert result["contradiction_type"] == "stated_dominance_not_observed"
        assert "D" in result["flagged_dimensions"]
        assert result["flagged_dimensions"]["D"] == 65.0
        # 65 / 200 = 0.325 > 0.30 threshold
        assert result["threshold_exceeded"] is True

    def test_conscientiousness_gap_detected(self) -> None:
        """High C on CV, low C on platform → conscientiousness_performance_gap."""
        cv = _scores(d=50, i=50, s=50, c=90)
        plat = _scores(d=50, i=50, s=50, c=30)
        result = compute_contradiction_score(cv, plat)

        assert result["contradiction_type"] == "conscientiousness_performance_gap"
        assert "C" in result["flagged_dimensions"]

    def test_stability_recovery_pattern(self) -> None:
        """Low S on CV, high S on platform → stability_recovery_pattern."""
        cv = _scores(d=50, i=50, s=25, c=50)
        plat = _scores(d=50, i=50, s=80, c=50)
        result = compute_contradiction_score(cv, plat)

        assert result["contradiction_type"] == "stability_recovery_pattern"
        assert "S" in result["flagged_dimensions"]

    def test_emerging_interpersonal_style(self) -> None:
        """Low I on CV, high I on platform → emerging_interpersonal_style."""
        cv = _scores(d=50, i=25, s=50, c=50)
        plat = _scores(d=50, i=80, s=50, c=50)
        result = compute_contradiction_score(cv, plat)

        assert result["contradiction_type"] == "emerging_interpersonal_style"
        assert "I" in result["flagged_dimensions"]

    def test_multi_dimension_divergence(self) -> None:
        """Multiple large gaps without a single pattern → multi_dimension_divergence."""
        cv = _scores(d=65, i=65, s=65, c=65)
        plat = _scores(d=25, i=25, s=25, c=25)
        result = compute_contradiction_score(cv, plat)

        assert result["contradiction_type"] == "multi_dimension_divergence"
        assert len(result["flagged_dimensions"]) == 4

    def test_divergent_contradiction_score_above_threshold(self) -> None:
        """Any significantly divergent profiles should exceed the 0.30 threshold."""
        cv = _scores(d=80, i=70, s=60, c=50)
        plat = _scores(d=20, i=30, s=40, c=80)
        result = compute_contradiction_score(cv, plat)

        assert result["contradiction_score"] > 0.30
        assert result["threshold_exceeded"] is True
        assert result["severity_tier"] in {
            "significant_contradiction",
            "high_contradiction",
            "severe_contradiction",
        }


# ===========================================================================
# Risk Scoring — Full 7 Categories
# ===========================================================================


class TestRiskScoringFullPipeline:
    """Compute all 7 risk categories from DISC + metrics."""

    def test_all_seven_categories_present(self) -> None:
        disc = _scores(d=50, i=50, s=50, c=50)
        prefs = _neutral_prefs()
        ca = _stable_career_analytics()
        bm = _healthy_behavioral_metrics()

        results = compute_risk_scores(disc, prefs, ca, bm)

        assert len(results) == 7
        categories = {r["category"] for r in results}
        expected = {
            "execution_risk",
            "collaboration_risk",
            "career_instability_risk",
            "overconfidence_risk",
            "avoidance_risk",
            "leadership_volatility_risk",
            "behavioral_contradiction_risk",
        }
        assert categories == expected

    def test_each_assessment_has_required_keys(self) -> None:
        disc = _scores(d=50, i=50, s=50, c=50)
        prefs = _neutral_prefs()
        results = compute_risk_scores(disc, prefs, {}, {})

        for r in results:
            assert "category" in r
            assert "score" in r
            assert "severity" in r
            assert "evidence" in r
            assert "is_flagged" in r
            assert r["severity"] in {"green", "yellow", "orange", "red"}
            assert 0.0 <= r["score"] <= 1.0

    def test_healthy_metrics_all_green(self) -> None:
        """Good metrics → all green across the board."""
        disc = _scores(d=50, i=50, s=50, c=50)
        prefs = _neutral_prefs()
        ca = _stable_career_analytics()
        bm = _healthy_behavioral_metrics()

        results = compute_risk_scores(disc, prefs, ca, bm)

        for r in results:
            assert r["severity"] == "green", (
                f"{r['category']} should be green, got {r['severity']} "
                f"(score={r['score']})"
            )
            assert r["is_flagged"] is False

    def test_risky_metrics_produce_flags(self) -> None:
        """Bad metrics → several categories should be flagged."""
        disc = _scores(d=80, i=50, s=30, c=30)
        prefs = PreferenceIndexes(
            stability_vs_growth=0.5,
            conservative_vs_aggressive_risk=0.5,
            control_vs_collaboration=0.5,
            short_term_vs_long_term=0.5,
            consistency_score=0.2,
        )
        ca = _risky_career_analytics()
        bm = _risky_behavioral_metrics()

        results = compute_risk_scores(disc, prefs, ca, bm)

        flagged = [r for r in results if r["is_flagged"]]
        assert len(flagged) >= 2, (
            f"Expected at least 2 flagged categories with risky inputs, "
            f"got {len(flagged)}"
        )

        # Execution risk should be high (low completion rate, high overdue)
        exec_risk = next(r for r in results if r["category"] == "execution_risk")
        assert exec_risk["score"] >= 0.45  # at least yellow

        # Career instability should be flagged
        career_risk = next(
            r for r in results if r["category"] == "career_instability_risk"
        )
        assert career_risk["score"] >= 0.45

    def test_overconfidence_risk_high_d_low_c(self) -> None:
        """High D + low C + persistent lateness → overconfidence risk."""
        disc = _scores(d=90, i=50, s=30, c=20)
        prefs = _neutral_prefs()
        bm = {"persistent_task_lateness_rate": 0.7}

        results = compute_risk_scores(disc, prefs, {}, bm)
        overconf = next(r for r in results if r["category"] == "overconfidence_risk")

        # D/100 * 0.40 + (1 - C/100) * 0.30 + lateness * 0.30
        # = 0.90*0.40 + 0.80*0.30 + 0.70*0.30 = 0.36 + 0.24 + 0.21 = 0.81
        assert overconf["score"] >= 0.75
        assert overconf["severity"] == "red"
        assert overconf["is_flagged"] is True

    def test_avoidance_risk_high_s_high_c(self) -> None:
        """High S + high C + slow responses + low initiative → avoidance risk."""
        disc = _scores(d=20, i=30, s=90, c=85)
        prefs = _neutral_prefs()
        bm = {
            "slow_deliberate_response_rate": 0.8,
            "project_initiative_rate": 0.1,
        }

        results = compute_risk_scores(disc, prefs, {}, bm)
        avoidance = next(r for r in results if r["category"] == "avoidance_risk")

        # S/100*0.25 + C/100*0.20 + slow*0.25 + (1-init)*0.30
        # = 0.90*0.25 + 0.85*0.20 + 0.80*0.25 + 0.90*0.30
        # = 0.225 + 0.170 + 0.200 + 0.270 = 0.865
        assert avoidance["score"] >= 0.70
        assert avoidance["severity"] == "red"
        assert avoidance["is_flagged"] is True

    def test_behavioral_contradiction_risk_tracks_score(self) -> None:
        """The behavioral_contradiction_risk directly reflects contradiction_score."""
        disc = _scores()
        prefs = _neutral_prefs()
        bm = {"contradiction_score": 0.65}

        results = compute_risk_scores(disc, prefs, {}, bm)
        beh_risk = next(
            r for r in results
            if r["category"] == "behavioral_contradiction_risk"
        )

        assert beh_risk["score"] == pytest.approx(0.65, abs=0.01)
        assert beh_risk["severity"] in {"orange", "red"}


# ===========================================================================
# Red Flag Generation from High Risk
# ===========================================================================


class TestRedFlagGenerationFromHighRisk:
    """Generate flags from orange/red risk assessments."""

    def test_no_flags_when_all_green(self) -> None:
        assessments = [
            {"category": "execution_risk", "score": 0.1, "severity": "green"},
            {"category": "collaboration_risk", "score": 0.15, "severity": "green"},
        ]
        contradiction = {"contradiction_score": 0.05, "flagged_dimensions": {}}
        flags = generate_red_flags(assessments, contradiction, user_id=USER_ID)

        # Only risk-based flags are emitted for orange/red
        risk_flags = [f for f in flags if "contradiction" not in f["flag_type"]]
        assert len(risk_flags) == 0

    def test_orange_assessment_generates_high_flag(self) -> None:
        assessments = [
            {
                "category": "execution_risk",
                "score": 0.65,
                "severity": "orange",
                "evidence": {"task_completion_rate": 0.4},
            },
        ]
        flags = generate_red_flags(assessments, {}, user_id=USER_ID)

        risk_flags = [f for f in flags if "execution" in f["flag_type"]]
        assert len(risk_flags) == 1
        flag = risk_flags[0]
        assert flag["flag_type"] == "high_execution_risk"
        assert flag["severity"] == "orange"
        assert flag["user_id"] == USER_ID
        assert "0.65" in flag["description"]

    def test_red_assessment_generates_critical_flag(self) -> None:
        assessments = [
            {
                "category": "overconfidence_risk",
                "score": 0.85,
                "severity": "red",
                "evidence": {"d_score": 90, "c_score": 20},
            },
        ]
        flags = generate_red_flags(assessments, {}, user_id=USER_ID)

        risk_flags = [f for f in flags if "overconfidence" in f["flag_type"]]
        assert len(risk_flags) == 1
        flag = risk_flags[0]
        assert flag["flag_type"] == "critical_overconfidence_risk"
        assert flag["severity"] == "red"

    def test_high_contradiction_generates_flag(self) -> None:
        """Contradiction score > 0.50 → high_contradiction flag."""
        contradiction = {
            "contradiction_score": 0.55,
            "contradiction_type": "stated_dominance_not_observed",
            "severity_tier": "high_contradiction",
            "flagged_dimensions": {"D": 50.0},
        }
        flags = generate_red_flags([], contradiction, user_id=USER_ID)

        overall_flags = [f for f in flags if f["flag_type"] == "high_contradiction"]
        assert len(overall_flags) == 1
        assert overall_flags[0]["severity"] == "orange"

        # Should also have per-dimension flag
        dim_flags = [f for f in flags if "dimension_contradiction" in f["flag_type"]]
        assert len(dim_flags) == 1
        assert dim_flags[0]["flag_type"] == "dimension_contradiction_d"

    def test_severe_contradiction_generates_red_flag(self) -> None:
        """Contradiction score > 0.70 → severe_contradiction flag."""
        contradiction = {
            "contradiction_score": 0.85,
            "contradiction_type": "multi_dimension_divergence",
            "severity_tier": "severe_contradiction",
            "flagged_dimensions": {"D": 60.0, "I": 40.0, "S": 35.0, "C": 50.0},
        }
        flags = generate_red_flags([], contradiction, user_id=USER_ID)

        severe_flags = [f for f in flags if f["flag_type"] == "severe_contradiction"]
        assert len(severe_flags) == 1
        assert severe_flags[0]["severity"] == "red"

        # 4 flagged dimensions → 4 dimension_contradiction flags
        dim_flags = [f for f in flags if "dimension_contradiction" in f["flag_type"]]
        assert len(dim_flags) == 4

    def test_multiple_flagged_assessments(self) -> None:
        """Multiple orange/red assessments → one flag per assessment."""
        assessments = [
            {"category": "execution_risk", "score": 0.65, "severity": "orange",
             "evidence": {}},
            {"category": "collaboration_risk", "score": 0.72, "severity": "red",
             "evidence": {}},
            {"category": "career_instability_risk", "score": 0.80, "severity": "red",
             "evidence": {}},
            {"category": "avoidance_risk", "score": 0.30, "severity": "green",
             "evidence": {}},
        ]
        flags = generate_red_flags(assessments, {}, user_id=USER_ID)

        # 3 flagged assessments → 3 flags
        assert len(flags) == 3
        types = {f["flag_type"] for f in flags}
        assert "high_execution_risk" in types
        assert "critical_collaboration_risk" in types
        assert "critical_career_instability_risk" in types

    def test_flag_metadata_includes_evidence(self) -> None:
        assessments = [
            {
                "category": "execution_risk",
                "score": 0.65,
                "severity": "orange",
                "evidence": {"task_completion_rate": 0.4, "avg_days_overdue": 7.0},
            },
        ]
        flags = generate_red_flags(assessments, {}, user_id=USER_ID)
        flag = flags[0]

        assert flag["metadata"]["category"] == "execution_risk"
        assert flag["metadata"]["score"] == 0.65
        assert "task_completion_rate" in flag["metadata"]["evidence"]


# ===========================================================================
# Full Risk Analysis Pipeline (analyze_user_risk)
# ===========================================================================


class TestFullRiskAnalysisPipeline:
    """End-to-end through analyze_user_risk worker."""

    @pytest.mark.asyncio
    async def test_full_pipeline_low_risk(self) -> None:
        """Aligned profiles + healthy metrics → green, no flags."""
        cv = _scores(d=55, i=50, s=50, c=55)
        plat = _scores(d=50, i=50, s=50, c=50)
        disc = _scores(d=52, i=50, s=50, c=52, dominant="D", secondary="C")

        result = await analyze_user_risk(
            cv_profile=cv,
            platform_profile=plat,
            disc_profile=disc,
            career_analytics=_stable_career_analytics(),
            behavioral_metrics=_healthy_behavioral_metrics(),
            user_id=USER_ID,
        )

        assert result["success"] is True
        assert result["error"] is None
        assert result["overall_risk_level"] == "green"
        assert result["flagged_count"] == 0
        assert len(result["risk_assessments"]) == 7

        # Contradiction should be low
        assert result["contradiction"]["contradiction_score"] < 0.15
        assert result["contradiction"]["threshold_exceeded"] is False

    @pytest.mark.asyncio
    async def test_full_pipeline_high_risk(self) -> None:
        """Divergent profiles + risky metrics → flagged, red flags generated."""
        cv = _scores(d=85, i=30, s=25, c=80)
        plat = _scores(d=25, i=70, s=70, c=30)
        disc = _scores(d=50, i=50, s=50, c=50)

        result = await analyze_user_risk(
            cv_profile=cv,
            platform_profile=plat,
            disc_profile=disc,
            preferences=PreferenceIndexes(
                stability_vs_growth=0.5,
                conservative_vs_aggressive_risk=0.5,
                control_vs_collaboration=0.5,
                short_term_vs_long_term=0.5,
                consistency_score=0.2,
            ),
            career_analytics=_risky_career_analytics(),
            behavioral_metrics=_risky_behavioral_metrics(),
            user_id=USER_ID,
        )

        assert result["success"] is True

        # Contradiction should be high (divergent CV vs platform)
        assert result["contradiction"]["threshold_exceeded"] is True
        assert result["contradiction"]["contradiction_score"] > 0.30

        # At least some categories should be flagged
        assert result["flagged_count"] >= 1

        # Red flags should be generated
        assert len(result["red_flags"]) >= 1

        # Overall risk should be elevated
        assert result["overall_risk_level"] in {"yellow", "orange", "red"}

    @pytest.mark.asyncio
    async def test_pipeline_without_cv_profile(self) -> None:
        """When CV profile is absent, contradiction detection is skipped."""
        plat = _scores(d=50, i=50, s=50, c=50)
        disc = _scores(d=50, i=50, s=50, c=50)

        result = await analyze_user_risk(
            cv_profile=None,
            platform_profile=plat,
            disc_profile=disc,
            user_id=USER_ID,
        )

        assert result["success"] is True
        assert result["contradiction"] == {}

    @pytest.mark.asyncio
    async def test_pipeline_without_platform_profile(self) -> None:
        """When platform profile is absent, contradiction detection is skipped."""
        cv = _scores(d=50, i=50, s=50, c=50)
        disc = _scores(d=50, i=50, s=50, c=50)

        result = await analyze_user_risk(
            cv_profile=cv,
            platform_profile=None,
            disc_profile=disc,
            user_id=USER_ID,
        )

        assert result["success"] is True
        assert result["contradiction"] == {}

    @pytest.mark.asyncio
    async def test_pipeline_with_no_optional_data(self) -> None:
        """Minimal input: only disc_profile — should still succeed.

        Note: with missing behavioral metrics, some defaults (0.0) cause
        formulas like ``(1 - project_initiative_rate) * 0.30`` to produce
        non-trivial risk scores, so not everything will be green.
        """
        disc = _scores(d=50, i=50, s=50, c=50)

        result = await analyze_user_risk(
            cv_profile=None,
            platform_profile=None,
            disc_profile=disc,
            user_id=USER_ID,
        )

        assert result["success"] is True
        assert result["contradiction"] == {}
        assert len(result["risk_assessments"]) == 7
        # Pipeline succeeds even with minimal data; some categories may
        # be yellow/orange due to formula defaults
        assert result["overall_risk_level"] in {"green", "yellow", "orange"}

    @pytest.mark.asyncio
    async def test_contradiction_feeds_into_behavioral_risk(self) -> None:
        """Contradiction score from detector should flow into behavioral_contradiction_risk."""
        cv = _scores(d=90, i=10, s=10, c=90)
        plat = _scores(d=10, i=90, s=90, c=10)
        disc = _scores(d=50, i=50, s=50, c=50)

        result = await analyze_user_risk(
            cv_profile=cv,
            platform_profile=plat,
            disc_profile=disc,
            user_id=USER_ID,
        )

        assert result["success"] is True

        # Contradiction should be severe
        c_score = result["contradiction"]["contradiction_score"]
        assert c_score > 0.50

        # behavioral_contradiction_risk should reflect the contradiction score
        beh_risk = next(
            r for r in result["risk_assessments"]
            if r["category"] == "behavioral_contradiction_risk"
        )
        assert beh_risk["score"] == pytest.approx(c_score, abs=0.01)

    @pytest.mark.asyncio
    async def test_result_structure_complete(self) -> None:
        """Verify the full result dict has all required keys."""
        disc = _scores(d=50, i=50, s=50, c=50)
        result = await analyze_user_risk(
            cv_profile=None,
            platform_profile=None,
            disc_profile=disc,
        )

        expected_keys = {
            "contradiction",
            "risk_assessments",
            "red_flags",
            "overall_risk_level",
            "flagged_count",
            "success",
            "error",
        }
        assert set(result.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_red_flags_include_contradiction_and_risk_flags(self) -> None:
        """When both risk and contradiction are high, both types of flags appear."""
        cv = _scores(d=90, i=10, s=10, c=90)
        plat = _scores(d=10, i=90, s=90, c=10)
        disc = _scores(d=80, i=30, s=30, c=20)

        result = await analyze_user_risk(
            cv_profile=cv,
            platform_profile=plat,
            disc_profile=disc,
            preferences=PreferenceIndexes(
                stability_vs_growth=0.5,
                conservative_vs_aggressive_risk=0.5,
                control_vs_collaboration=0.5,
                short_term_vs_long_term=0.5,
                consistency_score=0.1,
            ),
            career_analytics=_risky_career_analytics(),
            behavioral_metrics=_risky_behavioral_metrics(),
            user_id=USER_ID,
        )

        assert result["success"] is True
        flags = result["red_flags"]

        # Should have at least one contradiction-based flag
        contradiction_flags = [
            f for f in flags
            if "contradiction" in f["flag_type"]
        ]
        assert len(contradiction_flags) >= 1

        # Should have at least one risk-based flag
        risk_flags = [
            f for f in flags
            if "contradiction" not in f["flag_type"]
        ]
        assert len(risk_flags) >= 1
