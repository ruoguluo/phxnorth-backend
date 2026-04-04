"""Signal extractor service for processing behavioral events into DISC signals."""

from app.services.signal_extractor.confidence.calculator import (
    calculate_signal_confidence,
)
from app.services.signal_extractor.extractors.platform_signals import (
    extract_platform_signals,
)
from app.services.signal_extractor.validation.event_validator import validate_event
from app.services.signal_extractor.worker import process_behavioral_events

__all__ = [
    "calculate_signal_confidence",
    "extract_platform_signals",
    "process_behavioral_events",
    "validate_event",
]
