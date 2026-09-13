# vk_bot/src/constants.py
"""Общие константы проекта: VK, GigaChat, таймауты, лимиты."""

# Коды ошибок VK API
VK_ERROR_USER_BLOCKED = 901  # пользователь не принимает сообщения от группы

# GigaChat
GIGACHAT_API_PERS = "GIGACHAT_API_PERS"

# Пул соединений
DB_CONNECTION_POOL_MAX_SIZE = 8
DB_RETRY_MAX_ATTEMPTS = 3
DB_RETRY_BASE_DELAY = 0.5

# Интервал очистки спам-трекера (секунды)
SPAM_CLEANUP_INTERVAL_SECONDS = 300

# Ограничение истории спам-трекера (0 — без ограничения)
SPAM_RATELIMIT_MAXLEN = 200
SPAM_ADULT_VIOLATION_MAXLEN = 100

# Планировщик
SCHEDULER_DELAY_SECONDS = 0.2
SCHEDULER_HEALTH_INTERVAL_MINUTES = 10

# Очистка истории
PRUNE_KEEP_RECORDS = 500
PRUNE_TIME = "03:00"

__all__ = [
    "VK_ERROR_USER_BLOCKED",
    "GIGACHAT_API_PERS",
    "DB_CONNECTION_POOL_MAX_SIZE",
    "DB_RETRY_MAX_ATTEMPTS",
    "DB_RETRY_BASE_DELAY",
    "SPAM_CLEANUP_INTERVAL_SECONDS",
    "SPAM_RATELIMIT_MAXLEN",
    "SPAM_ADULT_VIOLATION_MAXLEN",
    "SCHEDULER_DELAY_SECONDS",
    "SCHEDULER_HEALTH_INTERVAL_MINUTES",
    "PRUNE_KEEP_RECORDS",
    "PRUNE_TIME",
]
