"""Signal confidence calculation module."""

from app.services.signal_extractor.confidence.calculator import (
    apply_temporal_decay,
    calculate_signal_confidence,
)

__all__ = ["calculate_signal_confidence", "apply_temporal_decay"]
