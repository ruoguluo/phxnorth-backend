"""Tests for the Red Flag Engine – immutable audit trail generation."""

from __future__ import annotations

import pytest

from app.services.risk_analyzer.red_flag_engine import generate_red_flags


# ---- helpers -----------------------------------------------------------------


def _risk(
    category: str = "execution_risk",
    score: float = 0.50,
    severity: str = "yellow",
    evidence: dict | None = None,
) -> dict:
    """Build a minimal risk assessment dict."""
    return {
        "category": category,
        "score": score,
        "severity": severity,
        "evidence": evidence or {},
        "is_flagged": severity in ("orange", "red"),
    }


def _contradiction(
    score: float = 0.0,
    contradiction_type: str = "none",
    severity_tier: str = "consistent",
    flagged_dimensions: dict | None = None,
) -> dict:
    """Build a minimal contradiction result dict."""
    return {
        "contradiction_score": score,
        "threshold_exceeded": score > 0.30,
        "dimension_gaps": {},
        "flagged_dimensions": flagged_dimensions or {},
        "contradiction_type": contradiction_type,
        "severity_tier": severity_tier,
    }


# ===========================================================================
# Return structure
# ===========================================================================


class TestFlagStructure:
    """Every red flag must have the required keys and correct types."""

    def test_flag_has_all_required_keys(self) -> None:
        flags = generate_red_flags(
            [_risk(severity="orange", score=0.65)],
            _contradiction(),
            user_id="u-123",
        )
        assert len(flags) == 1
        flag = flags[0]
        assert set(flag.keys()) == {
            "flag_type",
            "severity",
            "description",
            "metadata",
            "user_id",
        }

    def test_flag_type_is_string(self) -> None:
        flags = generate_red_flags(
            [_risk(severity="red", score=0.80)],
            _contradiction(),
        )
        assert isinstance(flags[0]["flag_type"], str)

    def test_severity_is_string(self) -> None:
        flags = generate_red_flags(
            [_risk(severity="orange")],
            _contradiction(),
        )
        assert flags[0]["severity"] in ("yellow", "orange", "red")

    def test_description_is_nonempty_string(self) -> None:
        flags = generate_red_flags(
            [_risk(severity="orange", score=0.62)],
            _contradiction(),
        )
        assert isinstance(flags[0]["description"], str)
        assert len(flags[0]["description"]) > 0

    def test_metadata_is_dict(self) -> None:
        flags = generate_red_flags(
            [_risk(severity="orange")],
            _contradiction(),
        )
        assert isinstance(flags[0]["metadata"], dict)

    def test_user_id_propagated(self) -> None:
        flags = generate_red_flags(
            [_risk(severity="orange")],
            _contradiction(),
            user_id="u-abc",
        )
        assert flags[0]["user_id"] == "u-abc"

    def test_user_id_none_by_default(self) -> None:
        flags = generate_red_flags(
            [_risk(severity="orange")],
            _contradiction(),
        )
        assert flags[0]["user_id"] is None


# ===========================================================================
# Risk-based flags
# ===========================================================================


class TestRiskBasedFlags:
    """Flags generated from risk assessments."""

    def test_green_severity_produces_no_flag(self) -> None:
        flags = generate_red_flags(
            [_risk(severity="green", score=0.20)],
            _contradiction(),
        )
        assert flags == []

    def test_yellow_severity_produces_no_flag(self) -> None:
        flags = generate_red_flags(
            [_risk(severity="yellow", score=0.45)],
            _contradiction(),
        )
        assert flags == []

    def test_orange_severity_produces_high_flag(self) -> None:
        flags = generate_red_flags(
            [_risk(category="execution_risk", severity="orange", score=0.62)],
            _contradiction(),
        )
        assert len(flags) == 1
        assert flags[0]["flag_type"] == "high_execution_risk"
        assert flags[0]["severity"] == "orange"

    def test_red_severity_produces_critical_flag(self) -> None:
        flags = generate_red_flags(
            [_risk(category="collaboration_risk", severity="red", score=0.78)],
            _contradiction(),
        )
        assert len(flags) == 1
        assert flags[0]["flag_type"] == "critical_collaboration_risk"
        assert flags[0]["severity"] == "red"

    def test_multiple_flagged_risks(self) -> None:
        assessments = [
            _risk(category="execution_risk", severity="orange", score=0.62),
            _risk(category="avoidance_risk", severity="green", score=0.30),
            _risk(category="collaboration_risk", severity="red", score=0.75),
        ]
        flags = generate_red_flags(assessments, _contradiction())
        flag_types = [f["flag_type"] for f in flags]
        assert "high_execution_risk" in flag_types
        assert "critical_collaboration_risk" in flag_types
        assert len(flags) == 2

    def test_risk_flag_metadata_contains_evidence(self) -> None:
        evidence = {"task_completion_rate": 0.4, "avg_days_overdue": 5.0}
        flags = generate_red_flags(
            [
                _risk(
                    category="execution_risk",
                    severity="orange",
                    score=0.65,
                    evidence=evidence,
                )
            ],
            _contradiction(),
        )
        meta = flags[0]["metadata"]
        assert meta["category"] == "execution_risk"
        assert meta["score"] == 0.65
        assert meta["evidence"] == evidence

    def test_risk_flag_description_contains_score(self) -> None:
        flags = generate_red_flags(
            [_risk(category="execution_risk", severity="orange", score=0.6234)],
            _contradiction(),
        )
        assert "0.62" in flags[0]["description"]

    def test_all_seven_categories_can_flag(self) -> None:
        categories = [
            "execution_risk",
            "collaboration_risk",
            "career_instability_risk",
            "overconfidence_risk",
            "avoidance_risk",
            "leadership_volatility_risk",
            "behavioral_contradiction_risk",
        ]
        assessments = [
            _risk(category=cat, severity="orange", score=0.60)
            for cat in categories
        ]
        flags = generate_red_flags(assessments, _contradiction())
        assert len(flags) == 7
        flag_types = {f["flag_type"] for f in flags}
        for cat in categories:
            assert f"high_{cat}" in flag_types


# ===========================================================================
# Contradiction-based flags
# ===========================================================================


class TestContradictionFlags:
    """Flags generated from contradiction analysis."""

    def test_low_contradiction_score_produces_no_flag(self) -> None:
        flags = generate_red_flags(
            [],
            _contradiction(score=0.30),
        )
        assert flags == []

    def test_score_at_050_produces_no_flag(self) -> None:
        # Threshold is strictly greater than 0.50
        flags = generate_red_flags(
            [],
            _contradiction(score=0.50),
        )
        assert flags == []

    def test_score_above_050_produces_high_contradiction(self) -> None:
        flags = generate_red_flags(
            [],
            _contradiction(score=0.55, contradiction_type="multi_dimension_divergence"),
        )
        assert len(flags) == 1
        assert flags[0]["flag_type"] == "high_contradiction"
        assert flags[0]["severity"] == "orange"

    def test_score_at_070_produces_high_not_severe(self) -> None:
        # 0.70 exactly: > 0.50 but not > 0.70
        flags = generate_red_flags(
            [],
            _contradiction(score=0.70),
        )
        assert len(flags) == 1
        assert flags[0]["flag_type"] == "high_contradiction"

    def test_score_above_070_produces_severe_contradiction(self) -> None:
        flags = generate_red_flags(
            [],
            _contradiction(
                score=0.85,
                contradiction_type="stated_dominance_not_observed",
                severity_tier="severe_contradiction",
            ),
        )
        assert len(flags) == 1
        assert flags[0]["flag_type"] == "severe_contradiction"
        assert flags[0]["severity"] == "red"

    def test_severe_does_not_also_emit_high(self) -> None:
        # A score > 0.70 should only produce severe, not both
        flags = generate_red_flags(
            [],
            _contradiction(score=0.80),
        )
        flag_types = [f["flag_type"] for f in flags]
        assert flag_types.count("severe_contradiction") == 1
        assert "high_contradiction" not in flag_types

    def test_contradiction_flag_metadata(self) -> None:
        flags = generate_red_flags(
            [],
            _contradiction(
                score=0.60,
                contradiction_type="stability_recovery_pattern",
                severity_tier="high_contradiction",
            ),
        )
        meta = flags[0]["metadata"]
        assert meta["contradiction_score"] == 0.60
        assert meta["contradiction_type"] == "stability_recovery_pattern"
        assert meta["severity_tier"] == "high_contradiction"

    def test_contradiction_description_contains_score(self) -> None:
        flags = generate_red_flags(
            [],
            _contradiction(score=0.55),
        )
        assert "0.55" in flags[0]["description"]


# ===========================================================================
# Dimension contradiction flags
# ===========================================================================


class TestDimensionContradictionFlags:
    """Flags for individual DISC dimension contradictions."""

    def test_single_flagged_dimension(self) -> None:
        flags = generate_red_flags(
            [],
            _contradiction(flagged_dimensions={"D": 40.0}),
        )
        assert len(flags) == 1
        assert flags[0]["flag_type"] == "dimension_contradiction_d"
        assert flags[0]["severity"] == "yellow"

    def test_multiple_flagged_dimensions(self) -> None:
        flags = generate_red_flags(
            [],
            _contradiction(flagged_dimensions={"D": 50.0, "C": 35.0}),
        )
        flag_types = {f["flag_type"] for f in flags}
        assert "dimension_contradiction_d" in flag_types
        assert "dimension_contradiction_c" in flag_types
        assert len(flags) == 2

    def test_all_four_dimensions_flagged(self) -> None:
        flags = generate_red_flags(
            [],
            _contradiction(
                flagged_dimensions={"D": 40.0, "I": 30.0, "S": 50.0, "C": 35.0}
            ),
        )
        flag_types = {f["flag_type"] for f in flags}
        assert flag_types == {
            "dimension_contradiction_d",
            "dimension_contradiction_i",
            "dimension_contradiction_s",
            "dimension_contradiction_c",
        }

    def test_dimension_flag_metadata_has_gap(self) -> None:
        flags = generate_red_flags(
            [],
            _contradiction(flagged_dimensions={"I": 45.0}, score=0.30),
        )
        meta = flags[0]["metadata"]
        assert meta["dimension"] == "I"
        assert meta["gap"] == 45.0
        assert meta["contradiction_score"] == 0.30

    def test_dimension_flag_description_mentions_gap(self) -> None:
        flags = generate_red_flags(
            [],
            _contradiction(flagged_dimensions={"S": 32.5}),
        )
        assert "32.5" in flags[0]["description"]
        assert "Steadiness" in flags[0]["description"]

    def test_dimension_flag_user_id_propagated(self) -> None:
        flags = generate_red_flags(
            [],
            _contradiction(flagged_dimensions={"D": 40.0}),
            user_id="u-xyz",
        )
        assert flags[0]["user_id"] == "u-xyz"


# ===========================================================================
# Combined scenarios
# ===========================================================================


class TestCombinedScenarios:
    """Full pipeline scenarios with both risk and contradiction inputs."""

    def test_no_flags_when_all_green_and_low_contradiction(self) -> None:
        assessments = [
            _risk(category="execution_risk", severity="green", score=0.20),
            _risk(category="collaboration_risk", severity="yellow", score=0.42),
        ]
        flags = generate_red_flags(
            assessments,
            _contradiction(score=0.10),
        )
        assert flags == []

    def test_combined_risk_and_contradiction_flags(self) -> None:
        assessments = [
            _risk(category="execution_risk", severity="orange", score=0.65),
            _risk(category="avoidance_risk", severity="red", score=0.78),
        ]
        contradiction = _contradiction(
            score=0.60,
            flagged_dimensions={"D": 40.0},
        )
        flags = generate_red_flags(assessments, contradiction, user_id="u-1")

        flag_types = [f["flag_type"] for f in flags]
        assert "high_execution_risk" in flag_types
        assert "critical_avoidance_risk" in flag_types
        assert "high_contradiction" in flag_types
        assert "dimension_contradiction_d" in flag_types
        assert len(flags) == 4

        # All should have user_id
        for flag in flags:
            assert flag["user_id"] == "u-1"

    def test_empty_inputs_produce_no_flags(self) -> None:
        flags = generate_red_flags([], _contradiction())
        assert flags == []

    def test_risk_flags_come_before_contradiction_flags(self) -> None:
        assessments = [_risk(severity="orange", score=0.60)]
        contradiction = _contradiction(score=0.55)
        flags = generate_red_flags(assessments, contradiction)
        assert flags[0]["flag_type"] == "high_execution_risk"
        assert flags[1]["flag_type"] == "high_contradiction"

    def test_severe_contradiction_with_dimension_flags(self) -> None:
        contradiction = _contradiction(
            score=0.85,
            flagged_dimensions={"D": 50.0, "I": 45.0, "S": 60.0, "C": 30.0},
            contradiction_type="multi_dimension_divergence",
            severity_tier="severe_contradiction",
        )
        flags = generate_red_flags([], contradiction)
        flag_types = [f["flag_type"] for f in flags]
        # 1 severe + 4 dimension flags = 5
        assert len(flags) == 5
        assert flag_types[0] == "severe_contradiction"
