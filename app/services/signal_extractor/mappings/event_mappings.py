"""Event-to-signal mapping rules for behavioral events to DISC dimensions."""

from typing import Any


# Event to DISC signal mappings
# Each event can map to multiple DISC dimensions with different weights
EVENT_SIGNAL_MAPPINGS: dict[str, dict[str, Any]] = {
    # Communication Events
    "MESSAGE_RESPONDED": {
        "signals": [
            {"dimension": "D", "weight": 0.3, "context": "responsiveness"},
            {"dimension": "I", "weight": 0.5, "context": "engagement"},
            {"dimension": "S", "weight": 0.4, "context": "reliability"},
        ],
        "modifiers": {
            "fast_response": {"D": 0.2, "I": 0.1},
            "slow_response": {"S": 0.2, "C": 0.1},
        },
    },
    "MESSAGE_SENT": {
        "signals": [
            {"dimension": "I", "weight": 0.6, "context": "initiative"},
            {"dimension": "D", "weight": 0.3, "context": "directness"},
        ],
    },
    "NOTIFICATION_OPENED": {
        "signals": [
            {"dimension": "I", "weight": 0.4, "context": "curiosity"},
            {"dimension": "C", "weight": 0.3, "context": "attention"},
        ],
    },
    
    # Task Events
    "TASK_COMPLETED": {
        "signals": [
            {"dimension": "C", "weight": 0.6, "context": "completion"},
            {"dimension": "D", "weight": 0.4, "context": "results"},
            {"dimension": "S", "weight": 0.3, "context": "follow_through"},
        ],
        "modifiers": {
            "early_completion": {"D": 0.3, "C": 0.2},
            "on_time": {"S": 0.2, "C": 0.3},
            "late": {"S": -0.2},
        },
    },
    "TASK_OVERDUE": {
        "signals": [
            {"dimension": "C", "weight": -0.4, "context": "discipline"},
            {"dimension": "S", "weight": -0.3, "context": "reliability"},
        ],
    },
    "TASK_STARTED": {
        "signals": [
            {"dimension": "D", "weight": 0.4, "context": "initiative"},
            {"dimension": "C", "weight": 0.3, "context": "planning"},
        ],
    },
    
    # Engagement Events
    "MENTORSHIP_REQUESTED": {
        "signals": [
            {"dimension": "I", "weight": 0.5, "context": "networking"},
            {"dimension": "C", "weight": 0.4, "context": "learning"},
            {"dimension": "S", "weight": 0.3, "context": "collaboration"},
        ],
    },
    "MENTORSHIP_COMPLETED": {
        "signals": [
            {"dimension": "S", "weight": 0.5, "context": "commitment"},
            {"dimension": "C", "weight": 0.4, "context": "follow_through"},
        ],
    },
    "MENTORSHIP_GIVEN": {
        "signals": [
            {"dimension": "I", "weight": 0.5, "context": "teaching"},
            {"dimension": "S", "weight": 0.5, "context": "support"},
        ],
    },
    "QUESTION_POSTED": {
        "signals": [
            {"dimension": "C", "weight": 0.5, "context": "inquiry"},
            {"dimension": "I", "weight": 0.4, "context": "engagement"},
        ],
        "modifiers": {
            "detailed_question": {"C": 0.3},
            "brief_question": {"D": 0.2},
        },
    },
    "QUESTION_ANSWERED": {
        "signals": [
            {"dimension": "I", "weight": 0.5, "context": "helpfulness"},
            {"dimension": "C", "weight": 0.4, "context": "expertise"},
        ],
    },
    
    # Assessment Events
    "ASSESSMENT_STARTED": {
        "signals": [
            {"dimension": "C", "weight": 0.5, "context": "self_awareness"},
            {"dimension": "D", "weight": 0.3, "context": "initiative"},
        ],
    },
    "ASSESSMENT_COMPLETE": {
        "signals": [
            {"dimension": "C", "weight": 0.6, "context": "thoroughness"},
            {"dimension": "S", "weight": 0.4, "context": "persistence"},
        ],
    },
    "ASSESSMENT_QUESTION_ANSWER": {
        "signals": [
            {"dimension": "C", "weight": 0.4, "context": "reflection"},
        ],
        "modifiers": {
            "quick_answer": {"D": 0.2},
            "thoughtful_answer": {"C": 0.3, "S": 0.2},
        },
    },
    
    # Navigation Events
    "PAGE_VIEW": {
        "signals": [
            {"dimension": "I", "weight": 0.3, "context": "exploration"},
            {"dimension": "C", "weight": 0.3, "context": "research"},
        ],
    },
    "NAVIGATION": {
        "signals": [
            {"dimension": "I", "weight": 0.4, "context": "exploration"},
        ],
    },
    "CLICK": {
        "signals": [
            {"dimension": "D", "weight": 0.3, "context": "action"},
            {"dimension": "I", "weight": 0.3, "context": "interest"},
        ],
    },
    "SCROLL": {
        "signals": [
            {"dimension": "C", "weight": 0.3, "context": "attention"},
        ],
        "modifiers": {
            "deep_scroll": {"C": 0.2},
            "shallow_scroll": {"D": 0.1},
        },
    },
    "HOVER": {
        "signals": [
            {"dimension": "C", "weight": 0.3, "context": "consideration"},
        ],
    },
    
    # Form Events
    "FORM_START": {
        "signals": [
            {"dimension": "C", "weight": 0.4, "context": "planning"},
        ],
    },
    "FORM_SUBMIT": {
        "signals": [
            {"dimension": "C", "weight": 0.5, "context": "completion"},
            {"dimension": "S", "weight": 0.4, "context": "follow_through"},
        ],
    },
    "FORM_ABANDON": {
        "signals": [
            {"dimension": "C", "weight": -0.3, "context": "discipline"},
            {"dimension": "S", "weight": -0.2, "context": "persistence"},
        ],
    },
    
    # Profile Events
    "PROFILE_UPLOAD": {
        "signals": [
            {"dimension": "D", "weight": 0.4, "context": "initiative"},
            {"dimension": "C", "weight": 0.3, "context": "preparation"},
        ],
    },
    "PROFILE_PARSE_COMPLETE": {
        "signals": [
            {"dimension": "C", "weight": 0.4, "context": "thoroughness"},
        ],
    },
    "PROFILE_UPDATED": {
        "signals": [
            {"dimension": "C", "weight": 0.5, "context": "accuracy"},
            {"dimension": "S", "weight": 0.3, "context": "maintenance"},
        ],
    },
    
    # Session Events
    "SESSION_START": {
        "signals": [
            {"dimension": "I", "weight": 0.4, "context": "engagement"},
            {"dimension": "D", "weight": 0.3, "context": "initiative"},
        ],
    },
    "SESSION_END": {
        "signals": [
            {"dimension": "S", "weight": 0.3, "context": "closure"},
        ],
        "modifiers": {
            "long_session": {"C": 0.2, "S": 0.2},
            "short_session": {"D": 0.2},
        },
    },
    
    # Error/Timeout Events
    "ERROR": {
        "signals": [
            {"dimension": "C", "weight": -0.2, "context": "precision"},
        ],
        "modifiers": {
            "user_error": {"C": -0.3},
            "system_error": {},
        },
    },
    "TIMEOUT": {
        "signals": [
            {"dimension": "S", "weight": -0.2, "context": "persistence"},
            {"dimension": "C", "weight": -0.2, "context": "attention"},
        ],
    },
    
    # Social Events
    "CONNECTION_REQUESTED": {
        "signals": [
            {"dimension": "I", "weight": 0.6, "context": "networking"},
            {"dimension": "D", "weight": 0.3, "context": "initiative"},
        ],
    },
    "CONNECTION_ACCEPTED": {
        "signals": [
            {"dimension": "I", "weight": 0.5, "context": "sociability"},
            {"dimension": "S", "weight": 0.3, "context": "openness"},
        ],
    },
    "CONTENT_SHARED": {
        "signals": [
            {"dimension": "I", "weight": 0.6, "context": "sharing"},
            {"dimension": "D", "weight": 0.3, "context": "influence"},
        ],
    },
    "CONTENT_LIKED": {
        "signals": [
            {"dimension": "I", "weight": 0.4, "context": "appreciation"},
            {"dimension": "S", "weight": 0.3, "context": "support"},
        ],
    },
    "COMMENT_POSTED": {
        "signals": [
            {"dimension": "I", "weight": 0.5, "context": "engagement"},
            {"dimension": "D", "weight": 0.3, "context": "opinion"},
        ],
    },
}


def get_event_mapping(event_type: str) -> dict[str, Any] | None:
    """
    Get the signal mapping for a specific event type.
    
    Args:
        event_type: The type of behavioral event
        
    Returns:
        Mapping dict or None if event type not found
    """
    return EVENT_SIGNAL_MAPPINGS.get(event_type)


def get_all_event_types() -> list[str]:
    """
    Get all supported event types.
    
    Returns:
        List of event type strings
    """
    return list(EVENT_SIGNAL_MAPPINGS.keys())


def get_dimensions_for_event(event_type: str) -> list[str]:
    """
    Get the DISC dimensions associated with an event type.
    
    Args:
        event_type: The type of behavioral event
        
    Returns:
        List of dimension strings (D, I, S, C)
    """
    mapping = get_event_mapping(event_type)
    if not mapping:
        return []
    
    dimensions = set()
    for signal in mapping.get("signals", []):
        dimensions.add(signal["dimension"])
    
    return list(dimensions)


def apply_context_modifier(
    event_type: str, 
    context: str, 
    base_signals: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Apply context modifiers to signal weights.
    
    Args:
        event_type: The type of behavioral event
        context: The context modifier to apply
        base_signals: Base signal mappings
        
    Returns:
        Modified signals with adjusted weights
    """
    mapping = get_event_mapping(event_type)
    if not mapping:
        return base_signals
    
    modifiers = mapping.get("modifiers", {})
    modifier = modifiers.get(context, {})
    
    if not modifier:
        return base_signals
    
    # Apply modifiers to signals
    modified_signals = []
    for signal in base_signals:
        modified_signal = signal.copy()
        dimension = signal["dimension"]
        if dimension in modifier:
            modified_signal["weight"] = signal["weight"] + modifier[dimension]
        modified_signals.append(modified_signal)
    
    return modified_signals
