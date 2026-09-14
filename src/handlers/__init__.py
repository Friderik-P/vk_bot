# vk_bot/src/handlers/__init__.py
"""Публичный интерфейс handlers."""

from .callback import handle_callback
from .message import handle_message

__all__ = ["handle_callback", "handle_message"]
