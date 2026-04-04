"""Signal weight definitions for DISC dimension scoring."""

from app.services.disc_scorer.weights.signal_weights import (
    SIGNAL_WEIGHTS,
    DISCWeights,
    SignalCategory,
    get_all_signal_types,
    get_cv_signals,
    get_platform_signals,
    get_signal_weight,
    get_signals_by_category,
)

__all__ = [
    "DISCWeights",
    "SIGNAL_WEIGHTS",
    "SignalCategory",
    "get_all_signal_types",
    "get_cv_signals",
    "get_platform_signals",
    "get_signal_weight",
    "get_signals_by_category",
]
