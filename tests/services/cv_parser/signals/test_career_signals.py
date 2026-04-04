"""Tests for career signal extractor."""

import pytest

from app.services.cv_parser.signals.career_signals import (
    _detect_career_gap,
    _detect_cross_industry_transition,
    _detect_diverse_functional_experience,
    _detect_executive_track,
    _detect_founder_experience,
    _detect_job_hopper_pattern,
    _detect_leadership_growth,
    _detect_long_tenure,
    _detect_rapid_transitions,
    _detect_short_tenure,
    _detect_stable_career,
    _detect_upward_progression,
    extract_career_signals,
)


class TestDetectShortTenure:
    """Tests for _detect_short_tenure function."""

    def test_detect_short_tenure_with_short_jobs(self):
        """Test detecting short tenure with short jobs."""
        job_entries = [
            {"company_name": "A", "job_title": "Dev", "duration_months": 6},
            {"company_name": "B", "job_title": "Dev", "duration_months": 8},
        ]
        analytics = {"short_tenure_count": 2, "short_tenure_rate": 1.0}
        result = _detect_short_tenure(job_entries, analytics)
        assert result is not None
        assert result["type"] == "short_tenure_detected"
        assert result["confidence"] > 0.5

    def test_detect_short_tenure_no_short_jobs(self):
        """Test no short tenure detected when no short jobs."""
        job_entries = [
            {"company_name": "A", "job_title": "Dev", "duration_months": 24},
        ]
        analytics = {"short_tenure_count": 0, "short_tenure_rate": 0.0}
        result = _detect_short_tenure(job_entries, analytics)
        assert result is None


class TestDetectRapidTransitions:
    """Tests for _detect_rapid_transitions function."""

    def test_detect_rapid_transitions_high_frequency(self):
        """Test detecting rapid transitions with high frequency."""
        job_entries = []
        analytics = {"transition_frequency": 2.0, "total_roles": 5}
        result = _detect_rapid_transitions(job_entries, analytics)
        assert result is not None
        assert result["type"] == "rapid_career_transitions"

    def test_detect_rapid_transitions_low_frequency(self):
        """Test no rapid transitions with low frequency."""
        job_entries = []
        analytics = {"transition_frequency": 0.5, "total_roles": 5}
        result = _detect_rapid_transitions(job_entries, analytics)
        assert result is None


class TestDetectLongTenure:
    """Tests for _detect_long_tenure function."""

    def test_detect_long_tenure_with_long_job(self):
        """Test detecting long tenure with job > 5 years."""
        job_entries = [
            {"company_name": "A", "job_title": "Dev", "duration_months": 72},
        ]
        analytics = {"longest_tenure_months": 72}
        result = _detect_long_tenure(job_entries, analytics)
        assert result is not None
        assert result["type"] == "long_tenure"

    def test_detect_long_tenure_no_long_job(self):
        """Test no long tenure detected with short jobs."""
        job_entries = [
            {"company_name": "A", "job_title": "Dev", "duration_months": 12},
        ]
        analytics = {"longest_tenure_months": 12}
        result = _detect_long_tenure(job_entries, analytics)
        assert result is None


class TestDetectCrossIndustryTransition:
    """Tests for _detect_cross_industry_transition function."""

    def test_detect_cross_industry_with_transitions(self):
        """Test detecting cross-industry transitions."""
        job_entries = []
        analytics = {"cross_industry_transitions": 2, "industry_diversity_score": 0.6}
        result = _detect_cross_industry_transition(job_entries, analytics)
        assert result is not None
        assert result["type"] == "cross_industry_transition"

    def test_detect_cross_industry_no_transitions(self):
        """Test no cross-industry when no transitions."""
        job_entries = []
        analytics = {"cross_industry_transitions": 0, "industry_diversity_score": 0.0}
        result = _detect_cross_industry_transition(job_entries, analytics)
        assert result is None


class TestDetectUpwardProgression:
    """Tests for _detect_upward_progression function."""

    def test_detect_upward_progression_with_moves(self):
        """Test detecting upward progression with upward moves."""
        job_entries = [
            {"company_name": "A", "job_title": "Junior Dev", "duration_months": 12},
            {"company_name": "B", "job_title": "Senior Dev", "duration_months": 24},
        ]
        analytics = {"upward_moves": 1, "downward_moves": 0, "total_roles": 2}
        result = _detect_upward_progression(job_entries, analytics)
        assert result is not None
        assert result["type"] == "consistent_upward_progression"

    def test_detect_upward_progression_no_moves(self):
        """Test no upward progression without moves."""
        job_entries = []
        analytics = {"upward_moves": 0, "downward_moves": 0, "total_roles": 1}
        result = _detect_upward_progression(job_entries, analytics)
        assert result is None


class TestDetectFounderExperience:
    """Tests for _detect_founder_experience function."""

    def test_detect_founder_with_founder_title(self):
        """Test detecting founder with founder title."""
        job_entries = [
            {
                "company_name": "Startup",
                "job_title": "Founder & CEO",
                "duration_months": 24,
                "description": "Founded the company",
            },
        ]
        analytics = {}
        result = _detect_founder_experience(job_entries, analytics)
        assert result is not None
        assert result["type"] == "founder_experience"

    def test_detect_founder_with_founder_description(self):
        """Test detecting founder with founder description."""
        job_entries = [
            {
                "company_name": "Startup",
                "job_title": "CEO",
                "duration_months": 24,
                "description": "Co-founded and built the company from scratch",
            },
        ]
        analytics = {}
        result = _detect_founder_experience(job_entries, analytics)
        assert result is not None
        assert result["type"] == "founder_experience"

    def test_detect_founder_no_founder_experience(self):
        """Test no founder detected without founder indicators."""
        job_entries = [
            {
                "company_name": "Corp",
                "job_title": "Developer",
                "duration_months": 24,
                "description": "Developed features",
            },
        ]
        analytics = {}
        result = _detect_founder_experience(job_entries, analytics)
        assert result is None


class TestDetectLeadershipGrowth:
    """Tests for _detect_leadership_growth function."""

    def test_detect_leadership_with_manager_title(self):
        """Test detecting leadership with manager title."""
        job_entries = [
            {
                "company_name": "Corp",
                "job_title": "Engineering Manager",
                "duration_months": 24,
                "description": "Managed team",
            },
        ]
        analytics = {"total_roles": 1}
        result = _detect_leadership_growth(job_entries, analytics)
        assert result is not None
        assert result["type"] == "leadership_growth"

    def test_detect_leadership_with_team_description(self):
        """Test detecting leadership with team management description."""
        job_entries = [
            {
                "company_name": "Corp",
                "job_title": "Lead Developer",
                "duration_months": 24,
                "description": "Led a team of 5 engineers",
            },
        ]
        analytics = {"total_roles": 1}
        result = _detect_leadership_growth(job_entries, analytics)
        assert result is not None
        assert result["type"] == "leadership_growth"

    def test_detect_leadership_no_leadership(self):
        """Test no leadership detected without leadership indicators."""
        job_entries = [
            {
                "company_name": "Corp",
                "job_title": "Developer",
                "duration_months": 24,
                "description": "Developed features",
            },
        ]
        analytics = {"total_roles": 1}
        result = _detect_leadership_growth(job_entries, analytics)
        assert result is None


class TestDetectStableCareer:
    """Tests for _detect_stable_career function."""

    def test_detect_stable_career_low_volatility(self):
        """Test detecting stable career with low volatility."""
        job_entries = [
            {"company_name": "A", "job_title": "Dev", "duration_months": 36},
            {"company_name": "B", "job_title": "Dev", "duration_months": 36},
        ]
        analytics = {
            "career_volatility_score": 0.1,
            "short_tenure_rate": 0.0,
            "avg_tenure_months": 36,
            "total_roles": 2,
        }
        result = _detect_stable_career(job_entries, analytics)
        assert result is not None
        assert result["type"] == "stable_career"

    def test_detect_stable_career_high_volatility(self):
        """Test no stable career with high volatility."""
        job_entries = []
        analytics = {
            "career_volatility_score": 0.7,
            "short_tenure_rate": 0.5,
            "avg_tenure_months": 8,
            "total_roles": 2,
        }
        result = _detect_stable_career(job_entries, analytics)
        assert result is None


class TestDetectJobHopperPattern:
    """Tests for _detect_job_hopper_pattern function."""

    def test_detect_job_hopper_high_short_rate(self):
        """Test detecting job hopper with high short tenure rate."""
        job_entries = [
            {"company_name": "A", "job_title": "Dev", "duration_months": 6},
            {"company_name": "B", "job_title": "Dev", "duration_months": 8},
            {"company_name": "C", "job_title": "Dev", "duration_months": 10},
            {"company_name": "D", "job_title": "Dev", "duration_months": 8},
        ]
        analytics = {
            "short_tenure_rate": 1.0,
            "transition_frequency": 2.0,
            "total_roles": 4,
            "avg_tenure_months": 8,
        }
        result = _detect_job_hopper_pattern(job_entries, analytics)
        assert result is not None
        assert result["type"] == "job_hopper_pattern"

    def test_detect_job_hopper_not_enough_roles(self):
        """Test no job hopper with too few roles."""
        job_entries = [
            {"company_name": "A", "job_title": "Dev", "duration_months": 6},
            {"company_name": "B", "job_title": "Dev", "duration_months": 6},
        ]
        analytics = {
            "short_tenure_rate": 1.0,
            "transition_frequency": 2.0,
            "total_roles": 2,
            "avg_tenure_months": 6,
        }
        result = _detect_job_hopper_pattern(job_entries, analytics)
        assert result is None


class TestDetectCareerGap:
    """Tests for _detect_career_gap function."""

    def test_detect_career_gap_with_gap_count(self):
        """Test detecting career gap with explicit gap count."""
        job_entries = []
        analytics = {"career_gap_count": 2, "total_gap_months": 12}
        result = _detect_career_gap(job_entries, analytics)
        assert result is not None
        assert result["type"] == "career_gap_detected"

    def test_detect_career_gap_inferred(self):
        """Test detecting career gap inferred from career span."""
        job_entries = [
            {"company_name": "A", "job_title": "Dev", "duration_months": 12},
        ]
        analytics = {"career_span_years": 5, "total_roles": 1}
        result = _detect_career_gap(job_entries, analytics)
        assert result is not None
        assert result["type"] == "career_gap_detected"
        assert result["evidence"]["inferred"] is True

    def test_detect_career_gap_no_gap(self):
        """Test no career gap detected."""
        job_entries = [
            {"company_name": "A", "job_title": "Dev", "duration_months": 24},
            {"company_name": "B", "job_title": "Dev", "duration_months": 24},
        ]
        analytics = {"career_span_years": 4, "total_roles": 2}
        result = _detect_career_gap(job_entries, analytics)
        assert result is None


class TestDetectDiverseFunctionalExperience:
    """Tests for _detect_diverse_functional_experience function."""

    def test_detect_diverse_functional_high_diversity(self):
        """Test detecting diverse functional experience."""
        job_entries = [
            {"company_name": "A", "job_title": "Engineer", "duration_months": 24},
            {"company_name": "B", "job_title": "Product Manager", "duration_months": 24},
        ]
        analytics = {"functional_diversity_score": 0.5, "total_roles": 2}
        result = _detect_diverse_functional_experience(job_entries, analytics)
        assert result is not None
        assert result["type"] == "diverse_functional_experience"

    def test_detect_diverse_functional_low_diversity(self):
        """Test no diverse functional with low diversity."""
        job_entries = [
            {"company_name": "A", "job_title": "Engineer", "duration_months": 24},
            {"company_name": "B", "job_title": "Engineer", "duration_months": 24},
        ]
        analytics = {"functional_diversity_score": 0.0, "total_roles": 2}
        result = _detect_diverse_functional_experience(job_entries, analytics)
        assert result is None


class TestDetectExecutiveTrack:
    """Tests for _detect_executive_track function."""

    def test_detect_executive_with_c_level(self):
        """Test detecting executive track with C-level title."""
        job_entries = [
            {
                "company_name": "Corp",
                "job_title": "Chief Technology Officer",
                "duration_months": 36,
            },
        ]
        analytics = {"upward_moves": 2, "total_roles": 3}
        result = _detect_executive_track(job_entries, analytics)
        assert result is not None
        assert result["type"] == "executive_track"

    def test_detect_executive_with_vp(self):
        """Test detecting executive track with VP title."""
        job_entries = [
            {
                "company_name": "Corp",
                "job_title": "VP of Engineering",
                "duration_months": 36,
            },
        ]
        analytics = {"upward_moves": 1, "total_roles": 2}
        result = _detect_executive_track(job_entries, analytics)
        assert result is not None
        assert result["type"] == "executive_track"

    def test_detect_executive_no_executive(self):
        """Test no executive track without executive roles."""
        job_entries = [
            {
                "company_name": "Corp",
                "job_title": "Manager",
                "duration_months": 36,
            },
        ]
        analytics = {"upward_moves": 1, "total_roles": 2}
        result = _detect_executive_track(job_entries, analytics)
        assert result is None


class TestExtractCareerSignals:
    """Tests for extract_career_signals function."""

    @pytest.mark.asyncio
    async def test_extract_career_signals_empty(self):
        """Test extracting signals from empty data."""
        result = await extract_career_signals([], {})
        assert result["success"] is True
        assert result["signal_count"] == 0
        assert result["signals"] == []

    @pytest.mark.asyncio
    async def test_extract_career_signals_job_hopper(self):
        """Test extracting signals for job hopper pattern."""
        job_entries = [
            {"company_name": "A", "job_title": "Dev", "duration_months": 6, "description": ""},
            {"company_name": "B", "job_title": "Dev", "duration_months": 8, "description": ""},
            {"company_name": "C", "job_title": "Dev", "duration_months": 10, "description": ""},
            {"company_name": "D", "job_title": "Dev", "duration_months": 8, "description": ""},
        ]
        analytics = {
            "total_roles": 4,
            "short_tenure_count": 4,
            "short_tenure_rate": 1.0,
            "avg_tenure_months": 8,
            "career_span_years": 2.7,
            "transition_frequency": 1.48,
            "cross_industry_transitions": 0,
            "upward_moves": 0,
            "lateral_moves": 0,
            "downward_moves": 0,
            "industry_diversity_score": 0.0,
            "functional_diversity_score": 0.0,
            "longest_tenure_months": 10,
            "career_volatility_score": 0.8,
        }
        result = await extract_career_signals(job_entries, analytics)
        assert result["success"] is True
        assert result["signal_count"] > 0
        signal_types = [s["type"] for s in result["signals"]]
        assert "job_hopper_pattern" in signal_types
        assert "short_tenure_detected" in signal_types

    @pytest.mark.asyncio
    async def test_extract_career_signals_stable_career(self):
        """Test extracting signals for stable career."""
        job_entries = [
            {"company_name": "A", "job_title": "Dev", "duration_months": 36, "description": ""},
            {"company_name": "B", "job_title": "Senior Dev", "duration_months": 48, "description": ""},
            {"company_name": "C", "job_title": "Lead Dev", "duration_months": 24, "description": "Led team"},
        ]
        analytics = {
            "total_roles": 3,
            "short_tenure_count": 0,
            "short_tenure_rate": 0.0,
            "avg_tenure_months": 36,
            "career_span_years": 9,
            "transition_frequency": 0.33,
            "cross_industry_transitions": 0,
            "upward_moves": 2,
            "lateral_moves": 0,
            "downward_moves": 0,
            "industry_diversity_score": 0.0,
            "functional_diversity_score": 0.0,
            "longest_tenure_months": 48,
            "career_volatility_score": 0.1,
        }
        result = await extract_career_signals(job_entries, analytics)
        assert result["success"] is True
        assert result["signal_count"] > 0
        signal_types = [s["type"] for s in result["signals"]]
        assert "stable_career" in signal_types
        assert "consistent_upward_progression" in signal_types

    @pytest.mark.asyncio
    async def test_extract_career_signals_founder_executive(self):
        """Test extracting signals for founder and executive."""
        job_entries = [
            {
                "company_name": "Startup",
                "job_title": "Founder & CEO",
                "duration_months": 36,
                "description": "Founded the company",
            },
            {
                "company_name": "Big Corp",
                "job_title": "VP of Engineering",
                "duration_months": 24,
                "description": "Led engineering team of 50",
            },
        ]
        analytics = {
            "total_roles": 2,
            "short_tenure_count": 0,
            "short_tenure_rate": 0.0,
            "avg_tenure_months": 30,
            "career_span_years": 5,
            "transition_frequency": 0.4,
            "cross_industry_transitions": 0,
            "upward_moves": 0,
            "lateral_moves": 0,
            "downward_moves": 0,
            "industry_diversity_score": 0.0,
            "functional_diversity_score": 0.0,
            "longest_tenure_months": 36,
            "career_volatility_score": 0.2,
        }
        result = await extract_career_signals(job_entries, analytics)
        assert result["success"] is True
        assert result["signal_count"] > 0
        signal_types = [s["type"] for s in result["signals"]]
        assert "founder_experience" in signal_types
        assert "executive_track" in signal_types
        assert "leadership_growth" in signal_types

    @pytest.mark.asyncio
    async def test_extract_career_signals_invalid_input(self):
        """Test handling invalid input."""
        result = await extract_career_signals(None, {})  # type: ignore
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_extract_career_signals_all_twelve_types(self):
        """Test that all 12 signal types can be detected."""
        # Create a comprehensive profile that triggers all signals
        job_entries = [
            {
                "company_name": "Tech Startup",
                "job_title": "Founder & CEO",
                "duration_months": 6,
                "description": "Founded and launched the company",
            },
            {
                "company_name": "Finance Corp",
                "job_title": "Junior Analyst",
                "duration_months": 8,
                "description": "Financial analysis",
            },
            {
                "company_name": "Big Tech",
                "job_title": "Engineering Manager",
                "duration_months": 72,
                "description": "Led team of 10 engineers",
            },
            {
                "company_name": "Healthcare Inc",
                "job_title": "CTO",
                "duration_months": 10,
                "description": "Chief Technology Officer",
            },
        ]
        analytics = {
            "total_roles": 4,
            "short_tenure_count": 3,
            "short_tenure_rate": 0.75,
            "avg_tenure_months": 24,
            "career_span_years": 8,
            "transition_frequency": 0.5,
            "cross_industry_transitions": 3,
            "upward_moves": 2,
            "lateral_moves": 0,
            "downward_moves": 0,
            "industry_diversity_score": 0.75,
            "functional_diversity_score": 0.75,
            "longest_tenure_months": 72,
            "career_volatility_score": 0.5,
            "career_gap_count": 1,
            "total_gap_months": 6,
        }
        result = await extract_career_signals(job_entries, analytics)
        assert result["success"] is True
        signal_types = [s["type"] for s in result["signals"]]
        
        # Check for key signal types
        expected_types = [
            "short_tenure_detected",
            "long_tenure",
            "cross_industry_transition",
            "consistent_upward_progression",
            "founder_experience",
            "leadership_growth",
            "job_hopper_pattern",
            "career_gap_detected",
            "diverse_functional_experience",
            "executive_track",
        ]
        
        for signal_type in expected_types:
            assert signal_type in signal_types, f"Missing signal type: {signal_type}"
