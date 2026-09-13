# vk_bot/src/filters/__init__.py
"""Публичный интерфейс filters."""

from .adult import is_adult_content, ADULT_RESPONSES
from .context import is_context_blocked, CONTEXT_RESPONSES
from .spam import analyze_message_for_spam

__all__ = [
    "is_adult_content",
    "ADULT_RESPONSES",
    "is_context_blocked",
    "CONTEXT_RESPONSES",
    "analyze_message_for_spam",
]
