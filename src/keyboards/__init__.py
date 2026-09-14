# vk_bot/src/keyboards/__init__.py
"""Публичный интерфейс keyboards."""

from .inline import get_admin_help_inline_keyboard
from .main_menu import get_main_menu_keyboard

__all__ = ["get_admin_help_inline_keyboard", "get_main_menu_keyboard"]
