# Chat → Behavioral Signals → 5D Model Update

**Date:** 2026-04-12
**Status:** Approved
**Scope:** Wire Kafka consumer pipeline + extract DISC signals from chat messages

## Problem

The DISC backend has a complete signal extraction and scoring pipeline, but:
1. The Kafka consumer was never instantiated — messages produced to topics are never consumed
2. Chat messages between mentors and mentees are a rich behavioral data source that isn't captured
3. The 5D model only updates from CV data — no ongoing behavioral signals feed into it

## Solution Overview

```
Mentorship Backend                    DISC Backend
┌─────────────────┐                  ┌──────────────────────────────┐
│ Chat message     │                  │                              │
│ saved to SQLite  │───HTTP POST────▶│ POST /api/v1/events          │
│                  │  (fire & forget) │      │                      │
│ classify_message │                  │      ▼                      │
│ into event types │                  │ Kafka: raw.behavioral.events │
└─────────────────┘                  │      │                      │
                                     │      ▼                      │
                                     │ Consumer (NEW)              │
                                     │      │                      │
                                     │      ▼                      │
                                     │ Signal Extractor (existing) │
                                     │      │                      │
                                     │      ▼                      │
                                     │ DISC Scorer (existing)      │
                                     │      │                      │
                                     │      ▼                      │
                                     │ Redis cache invalidated     │
                                     └──────────────────────────────┘
```

## Component 1: Kafka Consumer Bridge

**Location:** `app/kafka/event_consumer.py` (new file)
**Purpose:** Subscribe to `raw.behavioral.events`, process each message through the existing pipeline.

### Behavior

1. On DISC backend startup (in `main.py` lifespan), start an async background task
2. Task creates a `KafkaConsumerService` subscribed to `raw.behavioral.events`
3. For each message:
   - Deserialize as `BehavioralEventMessage`
   - Look up user by ID in PostgreSQL
   - Call `process_behavioral_events(user_id, events)` (existing signal extractor)
   - Call `compute_user_disc_profile(user_id)` (existing DISC scorer)
   - Invalidate Redis cache keys: `disc:{user_id}`, `risk:{user_id}`, `preference:{user_id}`
4. On failure: log error, continue to next message (don't block pipeline)
5. On shutdown: gracefully stop consumer

### Error handling

- Invalid message format → log + skip
- User not found → log + skip
- Signal extraction failure → log + skip (don't reprocess)
- Kafka unavailable at startup → log warning, don't start consumer (same pattern as producer)

### No DLQ for v1

Failed messages are logged and skipped. The DLQ infrastructure exists but adding retry logic adds complexity without clear benefit at this scale. Can be wired in later.

## Component 2: Chat Message Classifier

**Location:** `server/services/chat_signal_classifier.py` (new file in mentorship backend)
**Purpose:** Classify a chat message into zero or more behavioral event types.

### Rules

| # | Condition | Event Type | DISC |
|---|-----------|------------|------|
| 1 | Message length < 20 chars AND reply within 60s | `rapid_response` | D |
| 2 | Message length > 200 chars | `detailed_feedback` | C |
| 3 | Contains encouragement words (great, awesome, well done, good job, nice, excellent, proud) | `social_engagement` | I |
| 4 | Contains "?" or starts with how/what/why/when/where/who | `collaborative_inquiry` | S |
| 5 | Has file attachment (file_url is not null) | `resource_sharing` | C |
| 6 | First message in session by this user | `leadership_initiative` | D |
| 7 | Message contains numbered list or bullet points (regex: `^\s*[\d\-\*\•]`) | `structured_communication` | C |
| 8 | 3+ messages from same user within 2 minutes | `high_engagement` | I |

### Interface

```python
def classify_message(
    content: str,
    file_url: str | None,
    session_id: int,
    sender_id: int,
    created_at: datetime,
    db: Session,
) -> list[str]:
    """Returns list of event type strings, e.g. ['rapid_response', 'detailed_feedback']"""
```

### Rules for rule #1 and #8

These require looking at previous messages in the session (reply timing, message frequency). The function queries the last few messages from the `messages` table to make these determinations. This is a lightweight query (last 5 messages for the session) — not a performance concern.

## Component 3: Mentorship Backend → DISC Backend Event Dispatch

**Location:** `server/services/disc_event_dispatcher.py` (new file in mentorship backend)
**Purpose:** Fire-and-forget POST to DISC backend's `/api/v1/events` endpoint.

### Behavior

1. Called after a chat message is saved (in `messages.py` WebSocket handler and REST send endpoint)
2. Runs the classifier to get event types
3. If any events produced, POST to `http://localhost:8000/api/v1/events`
4. Uses the sender's JWT token for auth (already available in the request context)
5. Errors are logged and swallowed — chat should never fail because DISC backend is down

### Resolving the user's DISC UUID

The DISC backend events endpoint expects a DISC user UUID, not the mentorship integer ID. The dispatcher calls `GET /api/v1/users/me` with the user's JWT to resolve the UUID (same pattern the frontend uses). The UUID is cached in-memory per session to avoid repeated lookups.

### Payload format

```json
POST /api/v1/events
Authorization: Bearer <user_jwt>

{
  "events": [
    {
      "event_type": "rapid_response",
      "platform": "chat",
      "metadata": {
        "session_id": 9,
        "message_id": 42
      }
    },
    {
      "event_type": "detailed_feedback",
      "platform": "chat",
      "metadata": {
        "session_id": 9,
        "message_id": 42
      }
    }
  ]
}
```

This matches the existing `/api/v1/events` schema — no changes needed to the DISC backend endpoint.

## Component 4: Events Endpoint Fix

The existing `POST /api/v1/events` endpoint produces to Kafka but the events are also directly processable. Currently it only publishes to Kafka and returns 202. Since the consumer will now process from Kafka, this is fine. But we need to ensure:

1. The endpoint still works when Kafka is down (it already handles `kafka_producer = None`)
2. When Kafka is down, it should fall back to synchronous processing (call signal extractor + scorer directly), same pattern as CV upload

This is a small change to `app/api/v1/events.py`: add a sync fallback path.

## What changes where

### DISC Backend (`/Users/apple/Projects/phxnorth-backend`)

| File | Change |
|------|--------|
| `app/kafka/event_consumer.py` | **NEW** — Kafka consumer background task |
| `app/main.py` | Start consumer task in lifespan (alongside existing producer) |
| `app/api/v1/events.py` | Add sync fallback when Kafka is unavailable |

### Mentorship Backend (`/Users/apple/Projects/PhxNorth/server`)

| File | Change |
|------|--------|
| `server/services/chat_signal_classifier.py` | **NEW** — Rule-based message classifier |
| `server/services/disc_event_dispatcher.py` | **NEW** — Fire-and-forget HTTP dispatch to DISC backend |
| `server/routers/messages.py` | Call dispatcher after message save (WS and REST paths) |

### No frontend changes

The 5D Snapshot page already fetches DISC scores from the API. Once the pipeline updates scores, the frontend will show updated values on next load without any code changes.

## What this does NOT include

- LLM-based message analysis (future upgrade — swap classifier implementation)
- Historical backfill of existing messages (could be a one-time script later)
- Real-time 5D score push to frontend via WebSocket (scores update on page reload)
- DLQ processing or retry logic (v2)
- New event types beyond the 8 chat-specific rules (the existing 34 types continue to work)

## Testing approach

1. Start DISC backend with Docker Compose (includes Kafka)
2. Start mentorship backend
3. Send chat messages between mentor and mentee
4. Verify: messages appear in `raw.behavioral.events` Kafka topic
5. Verify: consumer processes them (check logs)
6. Verify: `behavioral_events` table in PostgreSQL has new rows
7. Verify: `GET /api/v1/users/{id}/disc-profile` returns updated scores
8. Verify: 5D Snapshot page shows non-zero engagement-related scores
