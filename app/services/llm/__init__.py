"""Shared LLM client utilities (DeepSeek via OpenAI-compatible API)."""

from app.services.llm.client import LLMUnavailable, chat_json, llm_enabled

__all__ = ["chat_json", "llm_enabled", "LLMUnavailable"]
