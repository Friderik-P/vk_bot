# vk_bot/src/services/__init__.py
"""Публичный интерфейс сервисов бота."""

from .broadcaster import broadcast_hello
from .health import check_gigachat_manual, run_health_check

__all__ = ["broadcast_hello", "check_gigachat_manual", "run_health_check"]
