# vk_bot/src/handlers/__init__.py
"""Публичный интерфейс handlers."""

from .message import handle_message
from .callback import handle_callback
from .utils import normalize_text_for_triggers

__all__ = ["handle_message", "handle_callback", "normalize_text_for_triggers"]
