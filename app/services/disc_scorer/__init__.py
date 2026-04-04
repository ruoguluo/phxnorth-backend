"""DISC Scorer service for computing personality profiles from behavioral signals."""

from app.services.disc_scorer.preference_inference import (
    PreferenceIndexes,
    infer_preferences,
)
from app.services.disc_scorer.scorer import (
    CONFIDENCE_THRESHOLD,
    DEFAULT_LAMBDA_DECAY,
    MODEL_VERSION,
    SECONDARY_MIN_SCORE,
    DISCScores,
    WeightedSignal,
    compute_disc_scores,
    compute_time_weight,
    normalize_to_range,
)
from app.services.disc_scorer.shift_detector import (
    SHIFT_THRESHOLD,
    STRUCTURAL_THRESHOLD,
    compute_disc_distance,
    detect_personality_shift,
)
from app.services.disc_scorer.windows import (
    WINDOWS,
    compute_windowed_profiles,
)

__all__ = [
    "CONFIDENCE_THRESHOLD",
    "DEFAULT_LAMBDA_DECAY",
    "DISCScores",
    "MODEL_VERSION",
    "PreferenceIndexes",
    "SECONDARY_MIN_SCORE",
    "SHIFT_THRESHOLD",
    "STRUCTURAL_THRESHOLD",
    "WINDOWS",
    "WeightedSignal",
    "compute_disc_distance",
    "compute_disc_scores",
    "compute_time_weight",
    "detect_personality_shift",
    "infer_preferences",
    "compute_windowed_profiles",
    "normalize_to_range",
]
