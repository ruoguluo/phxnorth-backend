# Chat → Behavioral Signals → 5D Model Update — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the Kafka consumer pipeline so behavioral events from chat messages flow through signal extraction and update DISC profiles in real time.

**Architecture:** Mentorship backend classifies chat messages into behavioral event types, POSTs them to the DISC backend's existing events endpoint. A new Kafka consumer in the DISC backend reads from `raw.behavioral.events`, runs the signal extractor and DISC scorer, and invalidates cached profiles.

**Tech Stack:** Python 3.13, FastAPI, aiokafka, SQLAlchemy 2.0 (async), Redis, PostgreSQL, httpx (for async HTTP dispatch)

---

## File Structure

### DISC Backend (`/Users/apple/Projects/phxnorth-backend`)

| File | Action | Responsibility |
|------|--------|---------------|
| `app/kafka/event_consumer.py` | CREATE | Kafka consumer background task: subscribe, deserialize, call signal extractor + scorer, invalidate cache |
| `app/main.py` | MODIFY | Start consumer in lifespan alongside producer |
| `app/api/v1/events.py` | MODIFY | Add sync fallback when Kafka producer is unavailable |

### Mentorship Backend (`/Users/apple/Projects/PhxNorth/server`)

| File | Action | Responsibility |
|------|--------|---------------|
| `server/services/chat_signal_classifier.py` | CREATE | Rule-based message → event type classifier |
| `server/services/disc_event_dispatcher.py` | CREATE | Fire-and-forget async HTTP dispatch to DISC events endpoint |
| `server/routers/messages.py` | MODIFY | Call dispatcher after message save in WS and upload paths |

---

### Task 1: Kafka Event Consumer (`app/kafka/event_consumer.py`)

**Files:**
- Create: `app/kafka/event_consumer.py`

- [ ] **Step 1: Create the event consumer module**

```python
"""Kafka consumer that processes behavioral events through the signal extraction
and DISC scoring pipeline."""

import asyncio
import logging
from typing import Any

from app.cache.disc_cache import DISCProfileCache
from app.cache.redis_client import RedisCacheService
from app.database import async_session_factory
from app.kafka.consumer import KafkaConsumerService
from app.kafka.topics import KafkaTopic
from app.models.user import User
from app.services.signal_extractor.worker import process_behavioral_events
from app.services.disc_scorer.worker import compute_user_disc_profile
from app.services.disc_scorer.scorer import WeightedSignal

from sqlalchemy import select

logger = logging.getLogger(__name__)

CONSUMER_GROUP = "behavioral-events-processor"


async def _handle_event(message: dict[str, Any]) -> None:
    """Process a single behavioral event message from Kafka.

    1. Validate and extract user_id
    2. Run signal extractor
    3. Run DISC scorer with extracted signals
    4. Invalidate Redis cache for the user
    """
    user_id = message.get("user_id")
    event_type = message.get("event_type", "unknown")

    if not user_id:
        logger.warning("Skipping event with no user_id: %s", message.get("event_id"))
        return

    logger.info("Processing event %s for user %s (type: %s)",
                message.get("event_id", "?"), user_id, event_type)

    try:
        # Step 1: Run signal extractor on this event
        events_list = [message]
        extraction_result = await process_behavioral_events(
            events=events_list,
            user_id=user_id,
            window_days=90,
        )

        if not extraction_result.get("success"):
            logger.warning("Signal extraction failed for user %s: %s",
                           user_id, extraction_result.get("error"))
            return

        signals = extraction_result.get("signals", [])
        if not signals:
            logger.debug("No signals extracted from event %s for user %s",
                         event_type, user_id)
            return

        # Step 2: Convert signals to WeightedSignal format for scorer
        weighted_signals = []
        for sig in signals:
            weighted_signals.append(WeightedSignal(
                dimension=sig.get("dimension", "D"),
                weight=sig.get("weight", 0.0),
                confidence=sig.get("confidence", 0.5),
                source=sig.get("source", "platform"),
                timestamp=sig.get("timestamp"),
            ))

        if not weighted_signals:
            return

        # Step 3: Run DISC scorer
        score_result = await compute_user_disc_profile(
            signals=weighted_signals,
            user_id=user_id,
        )

        if not score_result.get("success"):
            logger.warning("DISC scoring failed for user %s: %s",
                           user_id, score_result.get("error"))
            return

        logger.info("Updated DISC profile for user %s: dominant=%s confidence=%.2f (%d signals)",
                     user_id,
                     score_result.get("dominant", "?"),
                     score_result.get("confidence", 0),
                     score_result.get("signal_count", 0))

    except Exception as e:
        logger.exception("Error processing event for user %s: %s", user_id, e)


async def _invalidate_user_cache(user_id: str, redis: RedisCacheService | None) -> None:
    """Invalidate all cached DISC profiles for a user."""
    if redis is None:
        return
    try:
        cache = DISCProfileCache(redis)
        await cache.invalidate(user_id)
        logger.debug("Invalidated DISC cache for user %s", user_id)
    except Exception as e:
        logger.warning("Cache invalidation failed for user %s: %s", user_id, e)


async def _handle_event_with_cache(message: dict[str, Any], redis: RedisCacheService | None) -> None:
    """Wrapper that processes event and invalidates cache."""
    await _handle_event(message)
    user_id = message.get("user_id")
    if user_id:
        await _invalidate_user_cache(user_id, redis)


def create_event_consumer(redis: RedisCacheService | None = None) -> KafkaConsumerService:
    """Create a Kafka consumer for behavioral events."""

    async def handler(message: dict[str, Any]) -> None:
        await _handle_event_with_cache(message, redis)

    return KafkaConsumerService(
        topic=KafkaTopic.RAW_BEHAVIORAL_EVENTS.value,
        group_id=CONSUMER_GROUP,
        handler=handler,
    )
```

- [ ] **Step 2: Commit**

```bash
git add app/kafka/event_consumer.py
git commit -m "feat: add Kafka consumer for behavioral events pipeline"
```

---

### Task 2: Start Consumer in DISC Backend Lifespan

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Add consumer import and startup to lifespan**

Add import at the top of `app/main.py`:
```python
from app.kafka.event_consumer import create_event_consumer
```

In the lifespan function, after the Kafka producer startup block and before `yield`, add:

```python
    # Kafka consumer (optional, graceful degradation)
    kafka_consumer = None
    if kafka_producer is not None:
        try:
            kafka_consumer = create_event_consumer(redis=redis_cache)
            await kafka_consumer.start()
            logger.info("Kafka behavioral events consumer started")
        except Exception as exc:
            logger.warning("Kafka consumer failed to start: %s", exc)
            kafka_consumer = None
```

In the shutdown section (after `yield`), before stopping the producer, add:

```python
    if kafka_consumer is not None:
        await kafka_consumer.stop()
```

- [ ] **Step 2: Verify DISC backend starts without Kafka**

```bash
cd /Users/apple/Projects/phxnorth-backend
docker compose up -d postgres redis
docker compose up api
```

Expected: API starts, logs "Kafka producer failed to start" and "Kafka consumer failed to start" warnings, but serves health endpoint normally.

- [ ] **Step 3: Verify DISC backend starts with Kafka**

```bash
docker compose up -d
```

Expected: API starts, logs "Kafka behavioral events consumer started".

- [ ] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "feat: start Kafka behavioral events consumer in lifespan"
```

---

### Task 3: Sync Fallback in Events Endpoint

**Files:**
- Modify: `app/api/v1/events.py`

- [ ] **Step 1: Add sync fallback when Kafka is unavailable**

In `app/api/v1/events.py`, find the `_publish_events_to_kafka()` function. After the block where it checks `if producer is None`, add a synchronous fallback that calls the signal extractor directly.

Add import at top:
```python
from app.services.signal_extractor.worker import process_behavioral_events
```

At the end of `_publish_events_to_kafka()`, after the existing `if producer is None: return` block, change it to:

```python
    if producer is None:
        # Synchronous fallback: process events directly without Kafka
        logger.info("Kafka unavailable, processing %d events synchronously", len(validated))
        for event in validated:
            try:
                await process_behavioral_events(
                    events=[event.to_validator_dict()],
                    user_id=str(event.user_id),
                    window_days=90,
                )
            except Exception as exc:
                logger.warning("Sync event processing failed: %s", exc)
        return
```

- [ ] **Step 2: Commit**

```bash
git add app/api/v1/events.py
git commit -m "feat: add sync fallback for events endpoint when Kafka unavailable"
```

---

### Task 4: Chat Signal Classifier (Mentorship Backend)

**Files:**
- Create: `/Users/apple/Projects/PhxNorth/server/services/chat_signal_classifier.py`

- [ ] **Step 1: Create the services directory if needed**

```bash
mkdir -p /Users/apple/Projects/PhxNorth/server/services
touch /Users/apple/Projects/PhxNorth/server/services/__init__.py
```

- [ ] **Step 2: Create the classifier module**

```python
"""Classify chat messages into behavioral event types for DISC signal extraction.

Maps message patterns to existing DISC event types:
- MESSAGE_RESPONDED (with fast_response/slow_response modifiers)
- MESSAGE_SENT
- CONTENT_SHARED
- QUESTION_POSTED
- COMMENT_POSTED
"""

import re
from datetime import datetime
from sqlalchemy.orm import Session as DBSession
from models.message import Message

# Words indicating encouragement/social engagement
ENCOURAGEMENT_WORDS = {
    "great", "awesome", "well done", "good job", "nice", "excellent",
    "proud", "fantastic", "amazing", "brilliant", "wonderful", "perfect",
    "love it", "impressive", "outstanding", "bravo", "kudos",
}

# Regex for structured lists (numbered or bullet)
STRUCTURED_LIST_RE = re.compile(r"^\s*(\d+[\.\)]\s|[\-\*\•]\s)", re.MULTILINE)

# Regex for questions
QUESTION_RE = re.compile(
    r"\?|^(how|what|why|when|where|who|which|could you|can you|would you|do you)",
    re.IGNORECASE | re.MULTILINE,
)


def classify_message(
    content: str,
    file_url: str | None,
    session_id: int,
    sender_id: int,
    created_at: datetime,
    db: DBSession,
) -> list[dict]:
    """Classify a chat message into behavioral event types.

    Returns a list of event dicts, each with:
        {"event_type": str, "platform": "chat", "metadata": dict}
    """
    events: list[dict] = []
    meta = {"session_id": session_id, "sender_id": sender_id}

    # Rule 1: Rapid response (< 20 chars, replied within 60s)
    if len(content) < 20:
        prev_msg = (
            db.query(Message)
            .filter(
                Message.session_id == session_id,
                Message.sender_id != sender_id,
                Message.created_at < created_at,
            )
            .order_by(Message.created_at.desc())
            .first()
        )
        if prev_msg and (created_at - prev_msg.created_at).total_seconds() < 60:
            events.append({
                "event_type": "MESSAGE_RESPONDED",
                "platform": "chat",
                "payload": {**meta, "modifier": "fast_response"},
            })

    # Rule 2: Detailed feedback (> 200 chars)
    if len(content) > 200:
        events.append({
            "event_type": "MESSAGE_SENT",
            "platform": "chat",
            "payload": {**meta, "detail": "detailed_feedback", "length": len(content)},
        })

    # Rule 3: Encouragement / social engagement
    content_lower = content.lower()
    if any(word in content_lower for word in ENCOURAGEMENT_WORDS):
        events.append({
            "event_type": "COMMENT_POSTED",
            "platform": "chat",
            "payload": {**meta, "detail": "encouragement"},
        })

    # Rule 4: Questions / collaborative inquiry
    if QUESTION_RE.search(content):
        events.append({
            "event_type": "QUESTION_POSTED",
            "platform": "chat",
            "payload": {**meta, "detail": "collaborative_inquiry"},
        })

    # Rule 5: File attachment → resource sharing
    if file_url:
        events.append({
            "event_type": "CONTENT_SHARED",
            "platform": "chat",
            "payload": {**meta, "detail": "file_attachment", "file_url": file_url},
        })

    # Rule 6: First message in session → leadership initiative
    first_msg = (
        db.query(Message)
        .filter(
            Message.session_id == session_id,
            Message.id != None,
        )
        .order_by(Message.created_at.asc())
        .first()
    )
    if first_msg and first_msg.sender_id == sender_id:
        # Check if this is the first message ever (no messages before this one)
        earlier_count = (
            db.query(Message)
            .filter(
                Message.session_id == session_id,
                Message.created_at < created_at,
            )
            .count()
        )
        if earlier_count == 0:
            events.append({
                "event_type": "MENTORSHIP_REQUESTED",
                "platform": "chat",
                "payload": {**meta, "detail": "session_initiator"},
            })

    # Rule 7: Structured communication (numbered/bulleted lists)
    if STRUCTURED_LIST_RE.search(content):
        events.append({
            "event_type": "MESSAGE_SENT",
            "platform": "chat",
            "payload": {**meta, "detail": "structured_communication"},
        })

    # Rule 8: High engagement (3+ messages in 2 min)
    from datetime import timedelta
    two_min_ago = created_at - timedelta(minutes=2)
    recent_count = (
        db.query(Message)
        .filter(
            Message.session_id == session_id,
            Message.sender_id == sender_id,
            Message.created_at >= two_min_ago,
            Message.created_at <= created_at,
        )
        .count()
    )
    if recent_count >= 3:
        events.append({
            "event_type": "MESSAGE_SENT",
            "platform": "chat",
            "payload": {**meta, "detail": "high_engagement", "count_in_2min": recent_count},
        })

    # Always emit a base MESSAGE_SENT if no other events matched
    if not events:
        events.append({
            "event_type": "MESSAGE_SENT",
            "platform": "chat",
            "payload": meta,
        })

    return events
```

- [ ] **Step 3: Commit**

```bash
cd /Users/apple/Projects/PhxNorth
git add server/services/chat_signal_classifier.py server/services/__init__.py
git commit -m "feat: add rule-based chat message classifier for DISC signals"
```

---

### Task 5: DISC Event Dispatcher (Mentorship Backend)

**Files:**
- Create: `/Users/apple/Projects/PhxNorth/server/services/disc_event_dispatcher.py`

- [ ] **Step 1: Create the dispatcher module**

```python
"""Fire-and-forget dispatch of behavioral events to the DISC backend.

Sends classified chat events to POST /api/v1/events/batch on the DISC backend.
Errors are logged and swallowed — chat must never fail because DISC is down.
"""

import logging
import httpx
from datetime import datetime, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)

DISC_BACKEND_URL = "http://localhost:8000/api/v1"

# In-memory cache: JWT token -> DISC user UUID
_uuid_cache: dict[str, str] = {}


async def _resolve_disc_uuid(token: str) -> str | None:
    """Resolve the DISC backend UUID for the current user via /users/me."""
    if token in _uuid_cache:
        return _uuid_cache[token]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{DISC_BACKEND_URL}/users/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                uuid = data.get("id")
                if uuid:
                    _uuid_cache[token] = str(uuid)
                    return str(uuid)
    except Exception as e:
        logger.debug("Failed to resolve DISC UUID: %s", e)

    return None


async def dispatch_chat_events(
    events: list[dict],
    token: str,
) -> None:
    """Send behavioral events to DISC backend. Fire-and-forget.

    Args:
        events: List of event dicts from chat_signal_classifier
        token: JWT token of the message sender
    """
    if not events:
        return

    disc_uuid = await _resolve_disc_uuid(token)
    if not disc_uuid:
        logger.debug("Could not resolve DISC UUID, skipping event dispatch")
        return

    now = datetime.now(timezone.utc).isoformat()

    # Build batch payload matching DISC backend's BatchEventsIn schema
    batch = []
    for event in events:
        batch.append({
            "event_id": str(uuid4()),
            "user_id": disc_uuid,
            "event_type": event["event_type"],
            "timestamp": now,
            "payload": event.get("payload", {}),
        })

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{DISC_BACKEND_URL}/events/batch",
                json={"events": batch},
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code in (200, 201, 202):
                logger.info("Dispatched %d chat events to DISC backend for user %s",
                            len(batch), disc_uuid)
            else:
                logger.warning("DISC events dispatch returned %d: %s",
                               resp.status_code, resp.text[:200])
    except Exception as e:
        logger.debug("DISC events dispatch failed (non-critical): %s", e)
```

- [ ] **Step 2: Install httpx in the mentorship backend**

```bash
pip3 install --break-system-packages httpx
```

- [ ] **Step 3: Commit**

```bash
cd /Users/apple/Projects/PhxNorth
git add server/services/disc_event_dispatcher.py
git commit -m "feat: add fire-and-forget DISC event dispatcher for chat signals"
```

---

### Task 6: Wire Dispatcher into Messages Router

**Files:**
- Modify: `/Users/apple/Projects/PhxNorth/server/routers/messages.py`

- [ ] **Step 1: Add imports at top of `messages.py`**

```python
import asyncio
from services.chat_signal_classifier import classify_message
from services.disc_event_dispatcher import dispatch_chat_events
```

- [ ] **Step 2: Add helper function for async dispatch**

Add this function before the REST endpoints:

```python
def _dispatch_signals_background(
    content: str,
    file_url: str | None,
    session_id: int,
    sender_id: int,
    created_at,
    token: str,
    db: Session,
):
    """Classify message and dispatch signals in background (non-blocking)."""
    events = classify_message(
        content=content,
        file_url=file_url,
        session_id=session_id,
        sender_id=sender_id,
        created_at=created_at,
        db=db,
    )
    if events and token:
        asyncio.create_task(dispatch_chat_events(events, token))
```

- [ ] **Step 3: Call dispatcher in WebSocket message handler**

In the `websocket_endpoint` function, after the line `db.refresh(message)` and before the broadcast, add:

```python
                # Dispatch behavioral signals to DISC backend
                _dispatch_signals_background(
                    content=content,
                    file_url=None,
                    session_id=session_id,
                    sender_id=user.id,
                    created_at=message.created_at,
                    token=token,
                    db=db,
                )
```

- [ ] **Step 4: Call dispatcher in file upload endpoint**

In `upload_file_message()`, after `db.refresh(message)` and before the WS broadcast, add:

```python
    # Dispatch behavioral signals to DISC backend
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    events = classify_message(
        content=message.content,
        file_url=file_url,
        session_id=session_id,
        sender_id=current_user.id,
        created_at=message.created_at,
        db=db,
    )
    if events and token:
        asyncio.create_task(dispatch_chat_events(events, token))
```

Note: The upload endpoint needs `Request` as a dependency to get the auth header. Add `request: Request` to the function signature and `from fastapi import Request` to imports.

- [ ] **Step 5: Commit**

```bash
cd /Users/apple/Projects/PhxNorth
git add server/routers/messages.py
git commit -m "feat: wire chat signal classifier and DISC dispatcher into messages router"
```

---

### Task 7: End-to-End Verification

- [ ] **Step 1: Start all services**

```bash
# Terminal 1: DISC backend (with Kafka)
cd /Users/apple/Projects/phxnorth-backend
docker compose up -d

# Terminal 2: Mentorship backend
cd /Users/apple/Projects/PhxNorth/server
python3 -c "import uvicorn; uvicorn.run('main:app', host='0.0.0.0', port=8081)"

# Terminal 3: Frontend
cd /Users/apple/Projects/PhxNorth
npm run dev
```

- [ ] **Step 2: Verify Kafka consumer is running**

Check DISC backend logs:
```bash
cd /Users/apple/Projects/phxnorth-backend
docker compose logs api | grep -i "consumer"
```

Expected: `"Kafka behavioral events consumer started"`

- [ ] **Step 3: Send test chat messages**

Open two browser tabs:
1. Log in as `sarah.mentor@phxnorth.com` (mentor123) → go to a session
2. Log in as `chen.mentee@phxnorth.com` (mentee123) → go to the same session

Send several messages:
- Short reply ("ok") — should trigger `MESSAGE_RESPONDED` with `fast_response`
- Long message (>200 chars) — should trigger `MESSAGE_SENT` with `detailed_feedback`
- Encouraging message ("Great job!") — should trigger `COMMENT_POSTED`
- Question ("What do you think about this?") — should trigger `QUESTION_POSTED`
- Upload a file — should trigger `CONTENT_SHARED`

- [ ] **Step 4: Verify events were dispatched**

Check mentorship backend logs:
```bash
tail -20 /tmp/mentorship-backend.log | grep -i "dispatch"
```

Expected: `"Dispatched N chat events to DISC backend for user <uuid>"`

- [ ] **Step 5: Verify DISC profile was updated**

```bash
TOKEN=$(curl -s http://localhost:8081/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"chen.mentee@phxnorth.com","password":"mentee123"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -s "http://localhost:8000/api/v1/disc-profile-by-email?email=chen.mentee@phxnorth.com" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: DISC scores should show non-zero values reflecting the chat behavioral signals.

- [ ] **Step 6: Verify on frontend**

Reload the 5D Snapshot page or session detail page — scores should reflect the new behavioral data.

- [ ] **Step 7: Final commit and push**

```bash
cd /Users/apple/Projects/phxnorth-backend
git add -A && git push origin main

cd /Users/apple/Projects/PhxNorth
git add -A && git push origin main
```
