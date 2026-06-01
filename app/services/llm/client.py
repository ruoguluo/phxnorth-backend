"""Reusable DeepSeek (OpenAI-compatible) chat client.

Centralises the AsyncOpenAI setup that was previously inlined in the
CV-parser LLM extractor so that other features (e.g. question structuring)
can reuse the same configuration, JSON-parsing discipline, and error
handling.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)


class LLMUnavailable(RuntimeError):
    """Raised when the LLM cannot be used (no API key, disabled, or error).

    Callers that want graceful degradation should catch this and fall back
    to a non-AI code path.
    """


def llm_enabled() -> bool:
    """Return True if a DeepSeek API key is configured."""
    return bool(get_settings().deepseek_api_key)


def _strip_json_fences(content: str) -> str:
    """Remove markdown code fences some models add despite instructions."""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\n?", "", content)
        content = re.sub(r"\n?```$", "", content)
    return content


async def chat_json(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.2,
    max_tokens: int = 2000,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Run a single chat completion and parse the response as a JSON object.

    Args:
        system_prompt: System role content.
        user_prompt: User role content.
        temperature: Sampling temperature.
        max_tokens: Max tokens in the response.
        timeout: Request timeout in seconds.

    Returns:
        The parsed JSON object (a dict).

    Raises:
        LLMUnavailable: If no API key is set, or the call/parse fails.
    """
    settings = get_settings()

    if not settings.deepseek_api_key:
        logger.warning("llm.no_api_key", msg="DEEPSEEK_API_KEY not set")
        raise LLMUnavailable("DEEPSEEK_API_KEY not set")

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.llm_base_url,
        )

        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

        content = response.choices[0].message.content
        if not content:
            logger.warning("llm.empty_response")
            raise LLMUnavailable("Empty LLM response")

        data = json.loads(_strip_json_fences(content))
        if not isinstance(data, dict):
            logger.warning("llm.invalid_format", data_type=type(data).__name__)
            raise LLMUnavailable("LLM did not return a JSON object")

        return data

    except LLMUnavailable:
        raise
    except json.JSONDecodeError as e:
        logger.warning("llm.json_parse_error", error=str(e))
        raise LLMUnavailable(f"JSON parse error: {e}") from e
    except Exception as e:  # network, auth, etc.
        logger.warning("llm.api_error", error=str(e), error_type=type(e).__name__)
        raise LLMUnavailable(f"LLM API error: {e}") from e
