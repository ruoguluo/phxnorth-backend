# Signal Extractor Service

This service handles behavioral event processing and DISC personality signal extraction.

## Structure

```
signal_extractor/
├── __init__.py
├── mappings/
│   ├── __init__.py
│   └── event_mappings.py
└── processor.py
```

## Event-to-Signal Mapping

Events are mapped to DISC dimensions with weights and context modifiers.

### DISC Dimensions
- **D (Dominance)**: Decisiveness, directness, results-oriented
- **I (Influence)**: Communication, enthusiasm, sociability
- **S (Steadiness)**: Consistency, patience, supportiveness
- **C (Conscientiousness)**: Accuracy, analysis, detail-orientation

### Event Categories
- Communication: MESSAGE_RESPONDED, MESSAGE_SENT, etc.
- Task: TASK_COMPLETED, TASK_OVERDUE, etc.
- Engagement: MENTORSHIP_REQUESTED, QUESTION_POSTED, etc.
- Assessment: ASSESSMENT_STARTED, ASSESSMENT_COMPLETE, etc.
- Navigation: PAGE_VIEW, NAVIGATION, etc.

## Usage

```python
from app.services.signal_extractor.mappings import get_signal_mapping

mapping = get_signal_mapping("MESSAGE_RESPONDED")
```
