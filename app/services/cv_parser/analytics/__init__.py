"""Analytics module for CV Parser."""

from app.services.cv_parser.analytics.career_analytics import compute_career_analytics
from app.services.cv_parser.analytics.duration_calculator import calculate_durations

__all__ = ["calculate_durations", "compute_career_analytics"]
