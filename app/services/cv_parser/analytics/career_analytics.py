"""Career analytics module for computing comprehensive career metrics from job entries."""

from collections import Counter
from typing import Any


# Seniority levels for detecting career moves
SENIORITY_KEYWORDS = {
    "executive": ["ceo", "cto", "cfo", "cio", "coo", "chief", "president", "vp", "vice president"],
    "senior": ["senior", "sr.", "sr ", "lead", "principal", "staff", "architect"],
    "manager": ["manager", "director", "head of", "team lead"],
    "mid": ["analyst", "specialist", "coordinator", "associate", "engineer", "developer"],
    "junior": ["junior", "jr.", "jr ", "intern", "trainee", "assistant", "entry"],
}

# Common industry keywords
INDUSTRY_KEYWORDS = {
    "technology": ["software", "tech", "it", "computer", "digital", "saas", "startup"],
    "finance": ["bank", "financial", "investment", "fintech", "insurance", "trading"],
    "healthcare": ["health", "medical", "pharma", "biotech", "clinical", "hospital"],
    "consulting": ["consulting", "consultant", "advisory", "strategy"],
    "retail": ["retail", "e-commerce", "ecommerce", "consumer"],
    "manufacturing": ["manufacturing", "industrial", "production", "factory"],
    "education": ["education", "university", "school", "academic", "learning"],
    "media": ["media", "entertainment", "publishing", "marketing", "advertising"],
}

# Functional area keywords
FUNCTIONAL_KEYWORDS = {
    "engineering": ["engineer", "developer", "architect", "technical", "software"],
    "product": ["product", "pm", "product manager"],
    "sales": ["sales", "business development", "account executive"],
    "marketing": ["marketing", "growth", "brand", "content"],
    "operations": ["operations", "ops", "supply chain", "logistics"],
    "finance": ["finance", "accounting", "financial", "budget"],
    "hr": ["hr", "human resources", "talent", "recruiting", "people"],
    "legal": ["legal", "compliance", "regulatory", "counsel"],
}


def _detect_seniority_level(title: str) -> str:
    """
    Detect seniority level from job title.
    
    Args:
        title: Job title string
        
    Returns:
        Seniority level string
    """
    title_lower = title.lower()
    
    for level, keywords in SENIORITY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in title_lower:
                return level
    
    return "unknown"


def _detect_industry(company: str, title: str, description: str) -> str:
    """
    Detect industry from job entry.
    
    Args:
        company: Company name
        title: Job title
        description: Job description
        
    Returns:
        Industry string
    """
    text = f"{company} {title} {description}".lower()
    
    industry_scores = {}
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text)
        if score > 0:
            industry_scores[industry] = score
    
    if industry_scores:
        return max(industry_scores, key=industry_scores.get)
    
    return "unknown"


def _detect_functional_area(title: str, description: str) -> str:
    """
    Detect functional area from job entry.
    
    Args:
        title: Job title
        description: Job description
        
    Returns:
        Functional area string
    """
    text = f"{title} {description}".lower()
    
    function_scores = {}
    for function, keywords in FUNCTIONAL_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text)
        if score > 0:
            function_scores[function] = score
    
    if function_scores:
        return max(function_scores, key=function_scores.get)
    
    return "unknown"


def _calculate_diversity_score(items: list[str]) -> float:
    """
    Calculate diversity score (0-1) based on unique items.
    
    Args:
        items: List of items to analyze
        
    Returns:
        Diversity score between 0 and 1
    """
    if not items or len(items) <= 1:
        return 0.0
    
    # Filter out unknown values
    known_items = [item for item in items if item != "unknown"]
    
    if not known_items:
        return 0.0
    
    unique_count = len(set(known_items))
    total_count = len(known_items)
    
    # Score based on ratio of unique to total
    # More unique items = higher diversity
    diversity_ratio = unique_count / total_count
    
    # Scale to 0-1, with diminishing returns
    # 1 unique out of 1 = 0
    # 2 unique out of 2 = 0.5
    # 3 unique out of 3 = 0.67
    # 4 unique out of 4 = 0.75
    return round(min(1.0, diversity_ratio), 2)


def _detect_career_moves(job_entries: list[dict[str, Any]]) -> dict[str, int]:
    """
    Detect upward, lateral, and downward career moves.
    
    Args:
        job_entries: List of job entries sorted by date (oldest first)
        
    Returns:
        Dict with counts of each move type
    """
    moves = {
        "upward": 0,
        "lateral": 0,
        "downward": 0,
    }
    
    if len(job_entries) < 2:
        return moves
    
    # Sort entries by start date (oldest first)
    sorted_entries = sorted(
        job_entries,
        key=lambda x: x.get("start_date", "")
    )
    
    seniority_order = ["junior", "mid", "manager", "senior", "executive"]
    
    for i in range(1, len(sorted_entries)):
        prev_title = sorted_entries[i - 1].get("job_title", "")
        curr_title = sorted_entries[i].get("job_title", "")
        
        prev_level = _detect_seniority_level(prev_title)
        curr_level = _detect_seniority_level(curr_title)
        
        if prev_level == "unknown" or curr_level == "unknown":
            # Can't determine, skip
            continue
        
        try:
            prev_idx = seniority_order.index(prev_level)
            curr_idx = seniority_order.index(curr_level)
            
            if curr_idx > prev_idx:
                moves["upward"] += 1
            elif curr_idx < prev_idx:
                moves["downward"] += 1
            else:
                moves["lateral"] += 1
        except ValueError:
            # Level not in order list
            pass
    
    return moves


def _calculate_volatility_score(
    short_tenure_rate: float,
    transition_frequency: float,
    cross_industry_transitions: int,
    total_roles: int
) -> float:
    """
    Calculate career volatility score (0-1).
    
    Higher score indicates more volatile career patterns.
    
    Args:
        short_tenure_rate: Rate of short tenures (< 12 months)
        transition_frequency: Jobs per year
        cross_industry_transitions: Number of industry changes
        total_roles: Total number of roles
        
    Returns:
        Volatility score between 0 and 1
    """
    if total_roles <= 1:
        return 0.0
    
    # Normalize factors
    tenure_factor = min(1.0, short_tenure_rate)
    
    # Transition frequency: > 1 job per year is high volatility
    freq_factor = min(1.0, transition_frequency / 1.5)
    
    # Industry transitions: more than 2 is significant
    industry_factor = min(1.0, cross_industry_transitions / 3)
    
    # Weighted average
    volatility = (tenure_factor * 0.4 + freq_factor * 0.4 + industry_factor * 0.2)
    
    return round(volatility, 2)


def _detect_career_patterns(
    job_entries: list[dict[str, Any]],
    metrics: dict[str, Any]
) -> list[str]:
    """
    Detect career patterns from job entries and metrics.
    
    Args:
        job_entries: List of job entries
        metrics: Computed career metrics
        
    Returns:
        List of detected pattern strings
    """
    patterns = []
    
    # Early career pattern
    if metrics["total_roles"] <= 2 and metrics["career_span_years"] < 3:
        patterns.append("early_career")
    
    # Job hopper pattern
    if metrics["short_tenure_rate"] > 0.5 and metrics["total_roles"] > 3:
        patterns.append("job_hopper")
    
    # Stable career pattern
    if metrics["short_tenure_rate"] < 0.2 and metrics["avg_tenure_months"] > 24:
        patterns.append("stable_career")
    
    # Rapid progression pattern
    if metrics["upward_moves"] >= 2 and metrics["career_span_years"] < 5:
        patterns.append("rapid_progression")
    
    # Industry switcher pattern
    if metrics["cross_industry_transitions"] >= 2:
        patterns.append("industry_switcher")
    
    # Diverse experience pattern
    if metrics["industry_diversity_score"] > 0.5 or metrics["functional_diversity_score"] > 0.5:
        patterns.append("diverse_experience")
    
    # Long tenure pattern
    if metrics["longest_tenure_months"] > 48:
        patterns.append("long_tenure")
    
    # High volatility pattern
    if metrics["career_volatility_score"] > 0.6:
        patterns.append("high_volatility")
    
    # Low volatility pattern
    if metrics["career_volatility_score"] < 0.2 and metrics["total_roles"] > 2:
        patterns.append("low_volatility")
    
    # Frequent mover pattern
    if metrics["transition_frequency"] > 1.0:
        patterns.append("frequent_mover")
    
    # Lateral mover pattern
    if metrics["lateral_moves"] > metrics["upward_moves"]:
        patterns.append("lateral_mover")
    
    # Steady climber pattern
    if metrics["upward_moves"] > 0 and metrics["downward_moves"] == 0:
        patterns.append("steady_climber")
    
    return patterns


async def compute_career_analytics(job_entries: list[dict]) -> dict:
    """
    Compute comprehensive career analytics from job entries.
    
    Args:
        job_entries: List of job entries with duration_months, company, title, etc.
        
    Returns:
        dict with keys:
        - analytics: dict - all computed metrics
        - patterns: list[str] - detected career patterns
        - success: bool
        - error: str | None
    """
    try:
        if not job_entries:
            return {
                "analytics": {
                    "total_roles": 0,
                    "short_tenure_count": 0,
                    "short_tenure_rate": 0.0,
                    "avg_tenure_months": 0.0,
                    "career_span_years": 0.0,
                    "transition_frequency": 0.0,
                    "cross_industry_transitions": 0,
                    "upward_moves": 0,
                    "lateral_moves": 0,
                    "downward_moves": 0,
                    "industry_diversity_score": 0.0,
                    "functional_diversity_score": 0.0,
                    "longest_tenure_months": 0,
                    "career_volatility_score": 0.0,
                },
                "patterns": [],
                "success": True,
                "error": None,
            }
        
        # Basic metrics
        total_roles = len(job_entries)
        
        # Duration metrics
        durations = [
            entry.get("duration_months", 0) 
            for entry in job_entries 
            if entry.get("duration_months") is not None
        ]
        
        short_tenure_count = sum(1 for d in durations if d < 12)
        short_tenure_rate = short_tenure_count / total_roles if total_roles > 0 else 0.0
        avg_tenure_months = sum(durations) / len(durations) if durations else 0.0
        longest_tenure_months = max(durations) if durations else 0
        
        # Career span calculation
        total_months = sum(durations)
        career_span_years = total_months / 12
        
        # Transition frequency (jobs per year)
        transition_frequency = total_roles / career_span_years if career_span_years > 0 else 0.0
        
        # Detect industries and functional areas
        industries = []
        functions = []
        
        for entry in job_entries:
            company = entry.get("company_name", "")
            title = entry.get("job_title", "")
            description = entry.get("description", "")
            
            industry = _detect_industry(company, title, description)
            function = _detect_functional_area(title, description)
            
            industries.append(industry)
            functions.append(function)
        
        # Industry transitions
        cross_industry_transitions = 0
        for i in range(1, len(industries)):
            if industries[i] != industries[i-1] and industries[i] != "unknown":
                cross_industry_transitions += 1
        
        # Diversity scores
        industry_diversity_score = _calculate_diversity_score(industries)
        functional_diversity_score = _calculate_diversity_score(functions)
        
        # Career moves
        moves = _detect_career_moves(job_entries)
        upward_moves = moves["upward"]
        lateral_moves = moves["lateral"]
        downward_moves = moves["downward"]
        
        # Volatility score
        career_volatility_score = _calculate_volatility_score(
            short_tenure_rate,
            transition_frequency,
            cross_industry_transitions,
            total_roles
        )
        
        # Compile analytics
        analytics = {
            "total_roles": total_roles,
            "short_tenure_count": short_tenure_count,
            "short_tenure_rate": round(short_tenure_rate, 2),
            "avg_tenure_months": round(avg_tenure_months, 1),
            "career_span_years": round(career_span_years, 1),
            "transition_frequency": round(transition_frequency, 2),
            "cross_industry_transitions": cross_industry_transitions,
            "upward_moves": upward_moves,
            "lateral_moves": lateral_moves,
            "downward_moves": downward_moves,
            "industry_diversity_score": industry_diversity_score,
            "functional_diversity_score": functional_diversity_score,
            "longest_tenure_months": longest_tenure_months,
            "career_volatility_score": career_volatility_score,
        }
        
        # Detect patterns
        patterns = _detect_career_patterns(job_entries, analytics)
        
        return {
            "analytics": analytics,
            "patterns": patterns,
            "success": True,
            "error": None,
        }
        
    except Exception as e:
        return {
            "analytics": {},
            "patterns": [],
            "success": False,
            "error": f"Failed to compute career analytics: {str(e)}",
        }
