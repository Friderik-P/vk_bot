# vk_bot/src/scheduler/constants.py
"""Константы планировщика: текст рассылки и интервалы по умолчанию."""

from ..constants import (
    SCHEDULER_DELAY_SECONDS as DEFAULT_DELAY_SECONDS,
    SCHEDULER_HEALTH_INTERVAL_MINUTES as DEFAULT_HEALTH_INTERVAL_MINUTES,
    PRUNE_KEEP_RECORDS,
    PRUNE_TIME,
    BROADCAST_DELAY_SECONDS,
)

BROADCAST_MESSAGE = (
    "Про меня забыли((\n"
    "Мяф((\n"
    "Пообщаемся?"
)

__all__ = [
    "BROADCAST_MESSAGE",
    "DEFAULT_DELAY_SECONDS",
    "DEFAULT_HEALTH_INTERVAL_MINUTES",
    "PRUNE_KEEP_RECORDS",
    "PRUNE_TIME",
    "BROADCAST_DELAY_SECONDS",
]
