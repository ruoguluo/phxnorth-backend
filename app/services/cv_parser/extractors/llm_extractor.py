"""LLM-based job entry extractor using DeepSeek (OpenAI-compatible API).

Used as a fallback when the rule-based extractor produces low-confidence
results or fails to extract any entries from a CV.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from app.services.llm import LLMUnavailable, chat_json

logger = structlog.get_logger(__name__)

# System prompt for structured CV extraction
_SYSTEM_PROMPT = """\
You are a CV/resume parser. Extract job entries from the provided CV text.

Return a JSON object with a single key "job_entries" containing an array.
Each entry must have these fields:

- "job_title": string (e.g. "Senior Software Engineer")
- "company_name": string (e.g. "Google")
- "location": string or "" (e.g. "Mountain View, CA")
- "start_date": string in "YYYY-MM" format (e.g. "2022-01")
- "end_date": string in "YYYY-MM" format, or "Present" if current role
- "description": string (bullet points as plain text, joined by newlines)
- "industry": string or "" (e.g. "Technology", "Finance", "Healthcare")
- "seniority_level": one of "entry", "junior", "mid", "senior", "lead", "principal", "executive", or "" (use "entry" for interns/new grads, "executive" for directors/VPs/C-level)

Rules:
- Extract ALL job entries, including internships and short-term roles.
- If a date is ambiguous (e.g. just "2020"), use "2020-01" as the month.
- If no location is mentioned, use "".
- For seniority_level, infer from the job title if not explicitly stated.
- Return ONLY the JSON object, no markdown fences, no explanation.
"""

_USER_PROMPT_TEMPLATE = """\
Extract all job entries from this CV:

---
{cv_text}
---

Return the JSON object with "job_entries" array."""


async def extract_job_entries_llm(raw_text: str) -> list[dict[str, Any]]:
    """Extract job entries from CV text using DeepSeek LLM.

    Args:
        raw_text: The full raw text of the CV.

    Returns:
        List of job entry dicts matching the schema expected by the
        rest of the CV parser pipeline (company_name, job_title,
        start_date, end_date, location, description, confidence).
        Returns an empty list on any failure.
    """
    from app.config import get_settings

    settings = get_settings()

    if not settings.llm_cv_parser_enabled:
        logger.info("llm_extractor.disabled")
        return []

    # Truncate very long CVs to stay within token limits
    cv_text = raw_text[:8000] if len(raw_text) > 8000 else raw_text

    try:
        data = await chat_json(
            _SYSTEM_PROMPT,
            _USER_PROMPT_TEMPLATE.format(cv_text=cv_text),
            temperature=0.1,
            max_tokens=4000,
        )

        entries_raw = data.get("job_entries", [])
        if not isinstance(entries_raw, list):
            logger.warning("llm_extractor.invalid_format", data_type=type(entries_raw).__name__)
            return []

        # Normalize to the schema expected by the pipeline
        entries: list[dict[str, Any]] = []
        for raw in entries_raw:
            if not isinstance(raw, dict):
                continue

            entry: dict[str, Any] = {
                "company_name": str(raw.get("company_name", "")).strip(),
                "job_title": str(raw.get("job_title", "")).strip(),
                "start_date": str(raw.get("start_date", "")).strip(),
                "end_date": str(raw.get("end_date", "")).strip(),
                "location": str(raw.get("location", "")).strip(),
                "description": str(raw.get("description", "")).strip(),
                "confidence": 0.85,  # LLM extraction confidence
                # Bonus fields the rule-based parser doesn't provide
                "industry": str(raw.get("industry", "")).strip(),
                "seniority_level": str(raw.get("seniority_level", "")).strip(),
            }

            # Skip entries without at least a title or company
            if not entry["job_title"] and not entry["company_name"]:
                continue

            entries.append(entry)

        logger.info(
            "llm_extractor.success",
            entries_found=len(entries),
            model=settings.llm_model,
        )

        return entries

    except LLMUnavailable as e:
        # No API key, disabled, empty/invalid response, or upstream error.
        logger.info("llm_extractor.unavailable", reason=str(e))
        return []
    except json.JSONDecodeError as e:
        logger.warning("llm_extractor.json_parse_error", error=str(e))
        return []
    except Exception as e:
        logger.warning("llm_extractor.api_error", error=str(e), error_type=type(e).__name__)
        return []
