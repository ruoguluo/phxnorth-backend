"""Pydantic schemas for AI-assisted question structuring endpoints (FR-03).

These mirror the TypeScript interfaces used by the mentee question-entry
flow in the frontend (`MenteeQuestionEntry.tsx`).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# --- Shared sub-models ---


class AssumedGoal(BaseModel):
    """The AI's best guess at the mentee's concrete goal.

    Fields are category-dependent — only the relevant subset will be populated:
    - All categories: country, category, primaryGoal, timeHorizon
    - education: institution, programLevel, major, targetIntake
    - career: currentRole, targetRole, industry, yearsExperience
    - business: companyName, businessArea, challenge, revenue
    - entrepreneurship: ideaDescription, stage, fundingStatus, targetMarket
    """

    # Common fields
    country: str = ""
    category: str = ""
    primaryGoal: str = ""
    timeHorizon: str = ""

    # Education
    institution: str = ""
    programLevel: str = ""
    major: str = ""
    targetIntake: str = ""

    # Career
    currentRole: str = ""
    targetRole: str = ""
    industry: str = ""
    yearsExperience: str = ""

    # Business
    companyName: str = ""
    businessArea: str = ""
    challenge: str = ""
    revenue: str = ""

    # Entrepreneurship
    ideaDescription: str = ""
    ventureStage: str = ""
    fundingStatus: str = ""
    targetMarket: str = ""


class StageOption(BaseModel):
    """A selectable stage describing where the mentee is in their journey."""

    id: str
    label: str


class ClarificationQuestion(BaseModel):
    """A follow-up question the AI needs answered to refine understanding."""

    id: str
    question: str
    type: Literal["text", "select"] = "text"
    options: Optional[list[str]] = None


class AIUnderstanding(BaseModel):
    """Structured interpretation of the mentee's raw question."""

    country: str = ""
    category: str = ""
    subtype: str = ""
    stage: str = ""
    primaryGoal: str = ""
    timeHorizon: Optional[str] = None


class SubQuestion(BaseModel):
    """A single structured sub-question in a generated agenda."""

    id: str
    question: str
    purpose: str = ""
    depthLevel: Literal["Foundation", "Application", "Strategic"] = "Foundation"
    estimatedTime: int = 10


class StructuredQuestionData(BaseModel):
    """Normalised structured representation of the mentee's question."""

    domain: str = ""
    backgroundContext: str = ""
    desiredOutcome: str = ""
    timeHorizon: str = ""
    successCriteria: str = ""


# --- Requests ---


class InterpretRequest(BaseModel):
    """Request body for interpreting a raw mentee question."""

    raw_question: str = Field(
        ...,
        min_length=3,
        max_length=5000,
        description="The mentee's raw, free-text question.",
    )
    category: Optional[str] = Field(
        default=None,
        description="Optional category hint (education/career/business/entrepreneurship).",
    )
    country: Optional[str] = Field(default=None, description="Optional country hint.")


class AgendaRequest(BaseModel):
    """Request body for generating a structured agenda of sub-questions."""

    raw_question: str = Field(..., min_length=3, max_length=5000)
    understanding: Optional[AIUnderstanding] = None
    stage: Optional[str] = None
    answers: dict[str, str] = Field(
        default_factory=dict,
        description="Answers to any clarification questions, keyed by question id.",
    )


# --- Responses ---


class InterpretResponse(BaseModel):
    """Response for POST /questions/interpret."""

    understanding: AIUnderstanding
    assumedGoal: AssumedGoal
    stageOptions: list[StageOption] = Field(default_factory=list)
    clarificationQuestions: list[ClarificationQuestion] = Field(default_factory=list)
    ai_generated: bool = Field(
        default=True,
        description="False when the LLM was unavailable and a fallback was used.",
    )


class AgendaResponse(BaseModel):
    """Response for POST /questions/agenda."""

    subQuestions: list[SubQuestion] = Field(default_factory=list)
    structured: StructuredQuestionData
    ai_generated: bool = True
