# vk_bot/src/handlers/__init__.py
"""Публичный интерфейс handlers."""

from .message import handle_message
from .callback import handle_callback

__all__ = ["handle_message", "handle_callback"]
