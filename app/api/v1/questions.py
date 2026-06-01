"""AI-assisted question structuring endpoints (FR-03).

Helps a mentee turn a raw, free-text question into a structured interpretation
(an "understanding", an assumed goal, stage options, and clarification
questions) and, optionally, a structured agenda of sub-questions.

The endpoints are stateless with respect to the mentee's stored profile —
they operate purely on the supplied text — so the frontend can call this
backend for structuring and then create the mentorship request in the
mentorship service with the structured payload attached.

If the LLM is unavailable (no API key, disabled, or upstream error) the
endpoints degrade gracefully to a heuristic fallback and set
``ai_generated=False`` so the UI can adjust.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.v1.schemas.questions import (
    AgendaRequest,
    AgendaResponse,
    AIUnderstanding,
    AssumedGoal,
    ClarificationQuestion,
    InterpretRequest,
    InterpretResponse,
    StageOption,
    StructuredQuestionData,
    SubQuestion,
)
from app.config import get_settings
from app.models.user import User
from app.services.llm import LLMUnavailable, chat_json

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["questions"])


# --- Prompts ---

_INTERPRET_SYSTEM = """\
You are an intake assistant for a mentorship platform. A mentee has typed a
free-text question. Interpret it and return ONLY a JSON object with these keys:

- "understanding": object with
    "country" (string), "category" (one of "education","career","business",
    "entrepreneurship", or ""), "subtype" (string), "stage" (short string),
    "primaryGoal" (string), "timeHorizon" (string or null)
- "assumedGoal": object with
    "institution","programLevel","major","targetIntake","country","category"
    (all strings; use "" when unknown)
- "stageOptions": array of 3-6 objects, each {"id": short-slug, "label": string},
    representing the plausible stages the mentee might be at, most likely first
- "clarificationQuestions": array of 0-2 objects, each
    {"id": string, "question": string, "type": "text" or "select",
     "options": array of strings (only for type "select")}.
    Only include a clarification question when it is genuinely needed to give
    good guidance; otherwise return an empty array.

Rules:
- Infer fields from the question; never invent specific institutions unless the
  mentee clearly implies them.
- Return ONLY the JSON object, no markdown fences, no commentary.
"""

_INTERPRET_USER = """\
Mentee question:
---
{raw_question}
---
Category hint: {category}
Country hint: {country}

Return the JSON object."""

_AGENDA_SYSTEM = """\
You are a mentorship session planner. Given a mentee's question and context,
produce a focused agenda of sub-questions that a mentor and mentee should work
through. Return ONLY a JSON object with these keys:

- "subQuestions": array of 3-6 objects, each
    {"id": string, "question": string, "purpose": string,
     "depthLevel": one of "Foundation","Application","Strategic",
     "estimatedTime": integer minutes}
- "structured": object with
    "domain","backgroundContext","desiredOutcome","timeHorizon","successCriteria"
    (all strings; summarise from the inputs)

Rules:
- Order sub-questions from Foundation to Strategic.
- Keep estimatedTime realistic (5-20 minutes each).
- Return ONLY the JSON object, no markdown fences, no commentary.
"""

_AGENDA_USER = """\
Mentee question:
---
{raw_question}
---
Understanding: {understanding}
Selected stage: {stage}
Clarification answers: {answers}

Return the JSON object."""


# --- Fallback helpers (used when the LLM is unavailable) ---

_DEFAULT_STAGE_OPTIONS = [
    {"id": "exploring", "label": "Still exploring / deciding direction"},
    {"id": "planning", "label": "Planning my approach"},
    {"id": "in-progress", "label": "Actively working on it"},
    {"id": "stuck", "label": "Stuck on a specific problem"},
    {"id": "reviewing", "label": "Reviewing / finalising"},
]


def _guess_category(text: str, hint: str | None) -> str:
    if hint:
        return hint
    t = text.lower()
    if any(k in t for k in ("university", "admission", "degree", "study", "school", "phd", "major")):
        return "education"
    if any(k in t for k in ("startup", "founder", "co-founder", "venture", "mvp", "fundrais")):
        return "entrepreneurship"
    if any(k in t for k in ("revenue", "market", "sales", "company", "operations", "strategy")):
        return "business"
    if any(k in t for k in ("job", "career", "promotion", "interview", "resume", "role")):
        return "career"
    return ""


def _interpret_fallback(req: InterpretRequest) -> InterpretResponse:
    category = _guess_category(req.raw_question, req.category)
    return InterpretResponse(
        understanding=AIUnderstanding(
            country=req.country or "",
            category=category,
            subtype="",
            stage="",
            primaryGoal=req.raw_question.strip()[:200],
            timeHorizon=None,
        ),
        assumedGoal=AssumedGoal(country=req.country or "", category=category),
        stageOptions=[StageOption(**s) for s in _DEFAULT_STAGE_OPTIONS],
        clarificationQuestions=[],
        ai_generated=False,
    )


def _agenda_fallback(req: AgendaRequest) -> AgendaResponse:
    q = req.raw_question.strip()
    subs = [
        SubQuestion(
            id="q1",
            question="What is the core outcome you want from this?",
            purpose="Clarify the goal",
            depthLevel="Foundation",
            estimatedTime=10,
        ),
        SubQuestion(
            id="q2",
            question="What have you already tried or considered?",
            purpose="Establish context",
            depthLevel="Application",
            estimatedTime=10,
        ),
        SubQuestion(
            id="q3",
            question="What constraints or trade-offs matter most to you?",
            purpose="Surface decision criteria",
            depthLevel="Strategic",
            estimatedTime=15,
        ),
    ]
    return AgendaResponse(
        subQuestions=subs,
        structured=StructuredQuestionData(
            domain=(req.understanding.category if req.understanding else ""),
            backgroundContext="",
            desiredOutcome=q[:200],
            timeHorizon=(req.understanding.timeHorizon or "" if req.understanding else ""),
            successCriteria="",
        ),
        ai_generated=False,
    )


# --- Endpoints ---


@router.post(
    "/questions/interpret",
    response_model=InterpretResponse,
    summary="Interpret a mentee's raw question",
)
async def interpret_question(
    body: InterpretRequest,
    current_user: User = Depends(get_current_user),
) -> InterpretResponse:
    """Turn raw question text into a structured understanding + stage options."""
    settings = get_settings()
    if not settings.llm_question_assist_enabled or not settings.deepseek_api_key:
        return _interpret_fallback(body)

    try:
        data = await chat_json(
            _INTERPRET_SYSTEM,
            _INTERPRET_USER.format(
                raw_question=body.raw_question,
                category=body.category or "none",
                country=body.country or "none",
            ),
        )
    except LLMUnavailable:
        return _interpret_fallback(body)

    try:
        understanding = AIUnderstanding(**(data.get("understanding") or {}))
        assumed = AssumedGoal(**(data.get("assumedGoal") or {}))
        stage_opts = [
            StageOption(**s)
            for s in (data.get("stageOptions") or [])
            if isinstance(s, dict) and s.get("id") and s.get("label")
        ]
        clar = [
            ClarificationQuestion(**c)
            for c in (data.get("clarificationQuestions") or [])
            if isinstance(c, dict) and c.get("id") and c.get("question")
        ]
    except (TypeError, ValueError) as e:
        logger.warning("questions.interpret.bad_shape", error=str(e))
        return _interpret_fallback(body)

    if not stage_opts:
        stage_opts = [StageOption(**s) for s in _DEFAULT_STAGE_OPTIONS]

    return InterpretResponse(
        understanding=understanding,
        assumedGoal=assumed,
        stageOptions=stage_opts,
        clarificationQuestions=clar[:2],
        ai_generated=True,
    )


@router.post(
    "/questions/agenda",
    response_model=AgendaResponse,
    summary="Generate a structured agenda of sub-questions",
)
async def generate_agenda(
    body: AgendaRequest,
    current_user: User = Depends(get_current_user),
) -> AgendaResponse:
    """Produce a structured agenda (sub-questions) for a mentorship session."""
    settings = get_settings()
    if not settings.llm_question_assist_enabled or not settings.deepseek_api_key:
        return _agenda_fallback(body)

    understanding_str = (
        body.understanding.model_dump_json() if body.understanding else "none"
    )
    try:
        data = await chat_json(
            _AGENDA_SYSTEM,
            _AGENDA_USER.format(
                raw_question=body.raw_question,
                understanding=understanding_str,
                stage=body.stage or "none",
                answers=body.answers or {},
            ),
        )
    except LLMUnavailable:
        return _agenda_fallback(body)

    try:
        subs = [
            SubQuestion(**s)
            for s in (data.get("subQuestions") or [])
            if isinstance(s, dict) and s.get("question")
        ]
        structured = StructuredQuestionData(**(data.get("structured") or {}))
    except (TypeError, ValueError) as e:
        logger.warning("questions.agenda.bad_shape", error=str(e))
        return _agenda_fallback(body)

    if not subs:
        return _agenda_fallback(body)

    # Ensure ids exist/are unique.
    for i, sub in enumerate(subs, start=1):
        if not sub.id:
            sub.id = f"q{i}"

    return AgendaResponse(subQuestions=subs, structured=structured, ai_generated=True)
