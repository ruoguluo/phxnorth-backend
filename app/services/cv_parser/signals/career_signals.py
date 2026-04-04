"""Career signal extractor for identifying 12 types of career signals from job entries."""

from typing import Any


# Leadership keywords for detecting management track
LEADERSHIP_KEYWORDS = [
    "manager", "director", "head", "lead", "leading", "led",
    "team", "supervisor", "management", "managed",
]

# Founder/CEO keywords
FOUNDER_KEYWORDS = [
    "founder", "co-founder", "cofounder", "ceo", "chief executive",
    "owner", "partner", "entrepreneur", "started", "launched",
]

# Executive keywords
EXECUTIVE_KEYWORDS = [
    "ceo", "cto", "cfo", "cio", "coo", "chief", "president",
    "vp", "vice president", "executive",
]

# Promotion indicators
PROMOTION_KEYWORDS = [
    "promoted", "promotion", "advanced", "senior", "lead",
    "principal", "staff", "architect",
]


def _detect_short_tenure(job_entries: list[dict], analytics: dict) -> dict | None:
    """Detect short tenure pattern (jobs < 12 months)."""
    short_count = analytics.get("short_tenure_count", 0)
    short_rate = analytics.get("short_tenure_rate", 0.0)
    
    if short_count == 0:
        return None
    
    # Find jobs with short tenure
    short_jobs = [
        entry for entry in job_entries
        if entry.get("duration_months", 0) < 12
    ]
    
    confidence = min(1.0, 0.5 + (short_rate * 0.5))
    
    return {
        "type": "short_tenure_detected",
        "confidence": round(confidence, 2),
        "evidence": {
            "short_tenure_count": short_count,
            "short_tenure_rate": short_rate,
            "affected_jobs": [
                {
                    "company": job.get("company_name", ""),
                    "title": job.get("job_title", ""),
                    "duration_months": job.get("duration_months", 0),
                }
                for job in short_jobs[:3]  # Limit to first 3
            ],
        },
    }


def _detect_rapid_transitions(job_entries: list[dict], analytics: dict) -> dict | None:
    """Detect rapid career transitions (high transition frequency)."""
    transition_freq = analytics.get("transition_frequency", 0.0)
    total_roles = analytics.get("total_roles", 0)
    
    if transition_freq < 1.0 or total_roles < 3:
        return None
    
    confidence = min(1.0, transition_freq / 2.0)
    
    return {
        "type": "rapid_career_transitions",
        "confidence": round(confidence, 2),
        "evidence": {
            "transition_frequency": transition_freq,
            "total_roles": total_roles,
            "career_span_years": analytics.get("career_span_years", 0),
        },
    }


def _detect_long_tenure(job_entries: list[dict], analytics: dict) -> dict | None:
    """Detect long tenure pattern (jobs > 5 years / 60 months)."""
    longest_tenure = analytics.get("longest_tenure_months", 0)
    
    if longest_tenure < 60:
        return None
    
    # Find the long tenure job
    long_jobs = [
        entry for entry in job_entries
        if entry.get("duration_months", 0) >= 60
    ]
    
    confidence = min(1.0, longest_tenure / 120)  # Max confidence at 10 years
    
    return {
        "type": "long_tenure",
        "confidence": round(confidence, 2),
        "evidence": {
            "longest_tenure_months": longest_tenure,
            "long_tenure_jobs": [
                {
                    "company": job.get("company_name", ""),
                    "title": job.get("job_title", ""),
                    "duration_months": job.get("duration_months", 0),
                }
                for job in long_jobs[:2]
            ],
        },
    }


def _detect_cross_industry_transition(job_entries: list[dict], analytics: dict) -> dict | None:
    """Detect cross-industry transitions."""
    industry_transitions = analytics.get("cross_industry_transitions", 0)
    
    if industry_transitions < 1:
        return None
    
    confidence = min(1.0, 0.4 + (industry_transitions * 0.2))
    
    return {
        "type": "cross_industry_transition",
        "confidence": round(confidence, 2),
        "evidence": {
            "cross_industry_transitions": industry_transitions,
            "industry_diversity_score": analytics.get("industry_diversity_score", 0),
        },
    }


def _detect_upward_progression(job_entries: list[dict], analytics: dict) -> dict | None:
    """Detect consistent upward progression (promotions)."""
    upward_moves = analytics.get("upward_moves", 0)
    total_roles = analytics.get("total_roles", 0)
    
    if upward_moves < 1 or total_roles < 2:
        return None
    
    # Check for promotion keywords in job titles
    promotion_count = 0
    for entry in job_entries:
        title = entry.get("job_title", "").lower()
        if any(kw in title for kw in PROMOTION_KEYWORDS):
            promotion_count += 1
    
    progression_rate = upward_moves / (total_roles - 1) if total_roles > 1 else 0
    confidence = min(1.0, 0.5 + (progression_rate * 0.3) + (promotion_count * 0.1))
    
    return {
        "type": "consistent_upward_progression",
        "confidence": round(confidence, 2),
        "evidence": {
            "upward_moves": upward_moves,
            "downward_moves": analytics.get("downward_moves", 0),
            "promotion_keywords_found": promotion_count,
            "total_roles": total_roles,
        },
    }


def _detect_founder_experience(job_entries: list[dict], analytics: dict) -> dict | None:
    """Detect founder/CEO experience."""
    founder_jobs = []
    
    for entry in job_entries:
        title = entry.get("job_title", "").lower()
        description = entry.get("description", "").lower()
        
        # Check title for founder keywords
        title_match = any(kw in title for kw in FOUNDER_KEYWORDS)
        
        # Check description for founder indicators
        desc_indicators = [
            "founded", "started", "co-founded", "launched",
            "built from scratch", "bootstrap", "early stage",
        ]
        desc_match = any(ind in description for ind in desc_indicators)
        
        if title_match or desc_match:
            founder_jobs.append({
                "company": entry.get("company_name", ""),
                "title": entry.get("job_title", ""),
                "duration_months": entry.get("duration_months", 0),
            })
    
    if not founder_jobs:
        return None
    
    confidence = min(1.0, 0.7 + (len(founder_jobs) * 0.1))
    
    return {
        "type": "founder_experience",
        "confidence": round(confidence, 2),
        "evidence": {
            "founder_roles_count": len(founder_jobs),
            "founder_roles": founder_jobs[:3],
        },
    }


def _detect_leadership_growth(job_entries: list[dict], analytics: dict) -> dict | None:
    """Detect leadership growth (management track)."""
    leadership_jobs = []
    
    for entry in job_entries:
        title = entry.get("job_title", "").lower()
        description = entry.get("description", "").lower()
        
        # Check for leadership keywords
        title_match = any(kw in title for kw in LEADERSHIP_KEYWORDS)
        
        # Check description for team management indicators
        team_indicators = [
            "team of", "managed", "led a team", "supervised",
            "direct reports", "reporting to me", "my team",
        ]
        desc_match = any(ind in description for ind in team_indicators)
        
        if title_match or desc_match:
            leadership_jobs.append({
                "company": entry.get("company_name", ""),
                "title": entry.get("job_title", ""),
                "duration_months": entry.get("duration_months", 0),
            })
    
    if len(leadership_jobs) < 1:
        return None
    
    total_roles = analytics.get("total_roles", 0)
    leadership_ratio = len(leadership_jobs) / total_roles if total_roles > 0 else 0
    
    confidence = min(1.0, 0.5 + (leadership_ratio * 0.4))
    
    return {
        "type": "leadership_growth",
        "confidence": round(confidence, 2),
        "evidence": {
            "leadership_roles_count": len(leadership_jobs),
            "total_roles": total_roles,
            "leadership_ratio": round(leadership_ratio, 2),
            "leadership_roles": leadership_jobs[:3],
        },
    }


def _detect_stable_career(job_entries: list[dict], analytics: dict) -> dict | None:
    """Detect stable career pattern (low volatility)."""
    volatility = analytics.get("career_volatility_score", 1.0)
    short_rate = analytics.get("short_tenure_rate", 1.0)
    avg_tenure = analytics.get("avg_tenure_months", 0)
    total_roles = analytics.get("total_roles", 0)
    
    # Need at least 2 roles to assess stability
    if total_roles < 2:
        return None
    
    # Stable if low volatility and low short tenure rate
    if volatility > 0.3 or short_rate > 0.3:
        return None
    
    confidence = min(1.0, 1.0 - volatility + (avg_tenure / 60) * 0.3)
    
    return {
        "type": "stable_career",
        "confidence": round(confidence, 2),
        "evidence": {
            "career_volatility_score": volatility,
            "short_tenure_rate": short_rate,
            "avg_tenure_months": avg_tenure,
            "total_roles": total_roles,
        },
    }


def _detect_job_hopper_pattern(job_entries: list[dict], analytics: dict) -> dict | None:
    """Detect job hopper pattern (many short jobs)."""
    short_rate = analytics.get("short_tenure_rate", 0.0)
    total_roles = analytics.get("total_roles", 0)
    transition_freq = analytics.get("transition_frequency", 0.0)
    
    # Need multiple jobs to be a hopper
    if total_roles < 3:
        return None
    
    # Job hopper if > 50% short tenures or high transition frequency
    is_hopper = short_rate > 0.5 or (transition_freq > 1.5 and total_roles >= 4)
    
    if not is_hopper:
        return None
    
    confidence = min(1.0, short_rate + (transition_freq / 3))
    
    return {
        "type": "job_hopper_pattern",
        "confidence": round(confidence, 2),
        "evidence": {
            "short_tenure_rate": short_rate,
            "transition_frequency": transition_freq,
            "total_roles": total_roles,
            "avg_tenure_months": analytics.get("avg_tenure_months", 0),
        },
    }


def _detect_career_gap(job_entries: list[dict], analytics: dict) -> dict | None:
    """Detect career gaps (this would need gap data from duration calculator)."""
    # This signal requires gap information which comes from the duration calculator
    # For now, we infer from transition frequency and career span
    
    # If we have gap info in analytics (from duration calculator integration)
    gap_count = analytics.get("career_gap_count", 0)
    
    if gap_count > 0:
        confidence = min(1.0, 0.5 + (gap_count * 0.15))
        return {
            "type": "career_gap_detected",
            "confidence": round(confidence, 2),
            "evidence": {
                "gap_count": gap_count,
                "total_gaps_months": analytics.get("total_gap_months", 0),
            },
        }
    
    # Infer from career patterns - if transition frequency is unexpectedly low
    # given the career span, there might be gaps
    career_span = analytics.get("career_span_years", 0)
    total_roles = analytics.get("total_roles", 0)
    
    # Expected roles given career span (assuming avg 2-year tenure)
    expected_roles = career_span / 2 if career_span > 0 else 0
    
    # If significantly fewer roles than expected, might indicate gaps
    if career_span > 3 and total_roles < expected_roles * 0.7:
        confidence = min(1.0, 0.4 + (career_span - total_roles * 2) * 0.05)
        return {
            "type": "career_gap_detected",
            "confidence": round(confidence, 2),
            "evidence": {
                "career_span_years": career_span,
                "total_roles": total_roles,
                "expected_roles": round(expected_roles, 1),
                "inferred": True,
            },
        }
    
    return None


def _detect_diverse_functional_experience(job_entries: list[dict], analytics: dict) -> dict | None:
    """Detect diverse functional experience (multiple functions)."""
    func_diversity = analytics.get("functional_diversity_score", 0.0)
    total_roles = analytics.get("total_roles", 0)
    
    # Need at least 2 roles to have diversity
    if total_roles < 2:
        return None
    
    # Diversity score > 0.5 indicates multiple functions
    if func_diversity < 0.3:
        return None
    
    confidence = min(1.0, func_diversity + 0.2)
    
    return {
        "type": "diverse_functional_experience",
        "confidence": round(confidence, 2),
        "evidence": {
            "functional_diversity_score": func_diversity,
            "industry_diversity_score": analytics.get("industry_diversity_score", 0),
            "total_roles": total_roles,
        },
    }


def _detect_executive_track(job_entries: list[dict], analytics: dict) -> dict | None:
    """Detect executive track (C-suite progression)."""
    executive_jobs = []
    
    for entry in job_entries:
        title = entry.get("job_title", "").lower()
        
        if any(kw in title for kw in EXECUTIVE_KEYWORDS):
            executive_jobs.append({
                "company": entry.get("company_name", ""),
                "title": entry.get("job_title", ""),
                "duration_months": entry.get("duration_months", 0),
            })
    
    if not executive_jobs:
        return None
    
    # Check progression toward executive
    upward_moves = analytics.get("upward_moves", 0)
    total_roles = analytics.get("total_roles", 0)
    
    confidence = min(1.0, 0.6 + (len(executive_jobs) * 0.1) + (upward_moves * 0.05))
    
    return {
        "type": "executive_track",
        "confidence": round(confidence, 2),
        "evidence": {
            "executive_roles_count": len(executive_jobs),
            "upward_moves": upward_moves,
            "total_roles": total_roles,
            "executive_roles": executive_jobs[:3],
        },
    }


async def extract_career_signals(job_entries: list[dict], analytics: dict) -> dict:
    """
    Extract career signals from job entries and analytics.
    
    Args:
        job_entries: List of job entries
        analytics: Career analytics dict
        
    Returns:
        dict with keys:
        - signals: list[dict] - each with type, confidence, evidence
        - signal_count: int
        - success: bool
        - error: str | None
    """
    try:
        # Validate inputs
        if not isinstance(job_entries, list):
            return {
                "signals": [],
                "signal_count": 0,
                "success": False,
                "error": "job_entries must be a list",
            }
        
        if not isinstance(analytics, dict):
            return {
                "signals": [],
                "signal_count": 0,
                "success": False,
                "error": "analytics must be a dict",
            }
        
        # Collect all signal detectors
        detectors = [
            _detect_short_tenure,
            _detect_rapid_transitions,
            _detect_long_tenure,
            _detect_cross_industry_transition,
            _detect_upward_progression,
            _detect_founder_experience,
            _detect_leadership_growth,
            _detect_stable_career,
            _detect_job_hopper_pattern,
            _detect_career_gap,
            _detect_diverse_functional_experience,
            _detect_executive_track,
        ]
        
        # Run all detectors and collect signals
        signals = []
        for detector in detectors:
            try:
                signal = detector(job_entries, analytics)
                if signal is not None:
                    signals.append(signal)
            except Exception as e:
                # Log but don't fail the whole extraction
                continue
        
        # Sort by confidence (highest first)
        signals.sort(key=lambda x: x["confidence"], reverse=True)
        
        return {
            "signals": signals,
            "signal_count": len(signals),
            "success": True,
            "error": None,
        }
        
    except Exception as e:
        return {
            "signals": [],
            "signal_count": 0,
            "success": False,
            "error": f"Failed to extract career signals: {str(e)}",
        }
