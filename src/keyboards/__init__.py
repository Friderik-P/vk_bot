# vk_bot/src/keyboards/__init__.py
"""Публичный интерфейс keyboards."""

from .main_menu import get_main_menu_keyboard
from .inline import get_inline_keyboard, get_admin_help_inline_keyboard

__all__ = ["get_main_menu_keyboard", "get_inline_keyboard", "get_admin_help_inline_keyboard"]
