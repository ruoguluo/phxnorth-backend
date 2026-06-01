"""Tests for the AI question-structuring endpoints (FR-03).

The LLM is never called for real: we either rely on the no-API-key fallback
path or monkeypatch ``chat_json`` in the questions module.
"""

from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

from app.api.deps import get_current_user
from app.services.llm import LLMUnavailable


@pytest.fixture
def fake_user():
    """A minimal stand-in for the authenticated User object."""
    return SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        email="mentee@test.com",
        is_active=True,
    )


@pytest.fixture
def client_authed(app, fake_user) -> TestClient:
    """Test client with auth dependency overridden to a fake user."""
    app.dependency_overrides[get_current_user] = lambda: fake_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


def _enable_llm(monkeypatch):
    """Force the questions module to believe the LLM is enabled."""
    fake_settings = SimpleNamespace(
        llm_question_assist_enabled=True,
        deepseek_api_key="test-key",
    )
    monkeypatch.setattr(
        "app.api.v1.questions.get_settings", lambda: fake_settings
    )


# ---------------------------------------------------------------------------
# /questions/interpret
# ---------------------------------------------------------------------------


class TestInterpret:
    def test_fallback_when_no_api_key(self, client_authed):
        """With no API key, the endpoint degrades gracefully (ai_generated False)."""
        resp = client_authed.post(
            "/api/v1/questions/interpret",
            json={"raw_question": "How do I get into a UK chemistry program?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_generated"] is False
        # heuristic category detection
        assert data["understanding"]["category"] == "education"
        # always offers stage options so the UI can proceed
        assert len(data["stageOptions"]) >= 1
        assert data["clarificationQuestions"] == []

    def test_llm_success(self, client_authed, monkeypatch):
        _enable_llm(monkeypatch)

        async def fake_chat_json(system, user, **kwargs):
            return {
                "understanding": {
                    "country": "United Kingdom",
                    "category": "education",
                    "subtype": "undergraduate admissions",
                    "stage": "preparing",
                    "primaryGoal": "Get into Oxford chemistry",
                    "timeHorizon": "Fall 2027",
                },
                "assumedGoal": {
                    "institution": "University of Oxford",
                    "programLevel": "Undergraduate",
                    "major": "Chemistry",
                    "targetIntake": "Fall 2027",
                    "country": "United Kingdom",
                    "category": "Education",
                },
                "stageOptions": [
                    {"id": "deciding", "label": "Still deciding"},
                    {"id": "preparing", "label": "Preparing materials"},
                ],
                "clarificationQuestions": [
                    {
                        "id": "1",
                        "question": "Have you taken any standardized tests?",
                        "type": "select",
                        "options": ["Yes", "No"],
                    }
                ],
            }

        monkeypatch.setattr("app.api.v1.questions.chat_json", fake_chat_json)

        resp = client_authed.post(
            "/api/v1/questions/interpret",
            json={"raw_question": "Help me get into Oxford for chemistry"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_generated"] is True
        assert data["understanding"]["country"] == "United Kingdom"
        assert data["assumedGoal"]["institution"] == "University of Oxford"
        assert len(data["stageOptions"]) == 2
        assert data["clarificationQuestions"][0]["type"] == "select"

    def test_llm_unavailable_falls_back(self, client_authed, monkeypatch):
        _enable_llm(monkeypatch)

        async def boom(system, user, **kwargs):
            raise LLMUnavailable("upstream down")

        monkeypatch.setattr("app.api.v1.questions.chat_json", boom)

        resp = client_authed.post(
            "/api/v1/questions/interpret",
            json={"raw_question": "I want a new job in marketing"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_generated"] is False
        assert data["understanding"]["category"] == "career"

    def test_clarifications_capped_at_two(self, client_authed, monkeypatch):
        _enable_llm(monkeypatch)

        async def many(system, user, **kwargs):
            return {
                "understanding": {},
                "assumedGoal": {},
                "stageOptions": [],
                "clarificationQuestions": [
                    {"id": str(i), "question": f"Q{i}", "type": "text"}
                    for i in range(5)
                ],
            }

        monkeypatch.setattr("app.api.v1.questions.chat_json", many)
        resp = client_authed.post(
            "/api/v1/questions/interpret",
            json={"raw_question": "Question with lots of clarifications needed"},
        )
        data = resp.json()
        assert len(data["clarificationQuestions"]) == 2
        # empty stageOptions from LLM are backfilled with defaults
        assert len(data["stageOptions"]) >= 1

    def test_validation_rejects_short_question(self, client_authed):
        resp = client_authed.post(
            "/api/v1/questions/interpret", json={"raw_question": "x"}
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /questions/agenda
# ---------------------------------------------------------------------------


class TestAgenda:
    def test_fallback_when_no_api_key(self, client_authed):
        resp = client_authed.post(
            "/api/v1/questions/agenda",
            json={"raw_question": "How do I scale my startup's sales?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_generated"] is False
        assert len(data["subQuestions"]) >= 1
        # depth levels are valid enum members
        for sq in data["subQuestions"]:
            assert sq["depthLevel"] in {"Foundation", "Application", "Strategic"}

    def test_llm_success(self, client_authed, monkeypatch):
        _enable_llm(monkeypatch)

        async def fake_chat_json(system, user, **kwargs):
            return {
                "subQuestions": [
                    {
                        "id": "a1",
                        "question": "What does success look like?",
                        "purpose": "Define the goal",
                        "depthLevel": "Foundation",
                        "estimatedTime": 10,
                    },
                    {
                        "id": "a2",
                        "question": "What is your current funnel?",
                        "purpose": "Establish baseline",
                        "depthLevel": "Application",
                        "estimatedTime": 15,
                    },
                ],
                "structured": {
                    "domain": "business",
                    "backgroundContext": "early-stage startup",
                    "desiredOutcome": "scale sales",
                    "timeHorizon": "6 months",
                    "successCriteria": "2x revenue",
                },
            }

        monkeypatch.setattr("app.api.v1.questions.chat_json", fake_chat_json)
        resp = client_authed.post(
            "/api/v1/questions/agenda",
            json={
                "raw_question": "How do I scale sales?",
                "understanding": {"category": "business"},
                "stage": "in-progress",
                "answers": {},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_generated"] is True
        assert len(data["subQuestions"]) == 2
        assert data["structured"]["domain"] == "business"

    def test_empty_subquestions_falls_back(self, client_authed, monkeypatch):
        _enable_llm(monkeypatch)

        async def empty(system, user, **kwargs):
            return {"subQuestions": [], "structured": {}}

        monkeypatch.setattr("app.api.v1.questions.chat_json", empty)
        resp = client_authed.post(
            "/api/v1/questions/agenda",
            json={"raw_question": "A real question that needs an agenda"},
        )
        data = resp.json()
        assert data["ai_generated"] is False
        assert len(data["subQuestions"]) >= 1
