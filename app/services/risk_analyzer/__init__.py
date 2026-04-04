"""Risk Analyzer service for computing behavioral risk assessments."""

from app.services.risk_analyzer.contradiction_detector import (
    classify_contradiction,
    compute_contradiction_score,
    compute_disc_distance,
)
from app.services.risk_analyzer.red_flag_engine import generate_red_flags
from app.services.risk_analyzer.risk_predictor import (
    RISK_THRESHOLDS,
    compute_risk_scores,
)
from app.services.risk_analyzer.worker import analyze_user_risk

__all__ = [
    "RISK_THRESHOLDS",
    "analyze_user_risk",
    "classify_contradiction",
    "compute_contradiction_score",
    "compute_disc_distance",
    "compute_risk_scores",
    "generate_red_flags",
]
