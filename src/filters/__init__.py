# vk_bot/src/filters/__init__.py
"""Публичный интерфейс filters."""

from .adult import ADULT_RESPONSES, is_adult_content
from .context import CONTEXT_RESPONSES, is_context_blocked
from .spam import analyze_message_for_spam

__all__ = [
    "ADULT_RESPONSES",
    "CONTEXT_RESPONSES",
    "analyze_message_for_spam",
    "is_adult_content",
    "is_context_blocked",
]
