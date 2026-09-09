# vk_bot/src/db/__init__.py
"""
Публичный интерфейс модуля db.
Остальные файлы используют относительные импорты, а внешний код — этот __init__.
"""

from .connection import get_connection, close_connection, close_all_connections
from .schema import init_db

# Пользователи и игнор-лист
from .users import (
    load_peer_ids,
    add_peer_id,
    mark_user_blocked,
    get_blocked_ids,
)

# История чата
from .chat_history import (
    save_message,
    load_history,
    clear_chat_history,
    prune_all_history,
)

# Статистика
from .stats import increment_stats, get_stats

# Спам и 18+ (баны, лимиты, нарушения)
from .spam import (
    check_ratelimit,
    is_spam_banned,
    ban_for_spam,
    record_adult_violation,
    is_adult_banned,
)
from .admin_audit import log_admin_action, get_admin_audit

__all__ = [
    "get_connection",
    "close_connection",
    "close_all_connections",
    "init_db",
    "load_peer_ids",
    "add_peer_id",
    "mark_user_blocked",
    "get_blocked_ids",
    "save_message",
    "load_history",
    "clear_chat_history",
    "prune_all_history",
    "increment_stats",
    "get_stats",
    "check_ratelimit",
    "is_spam_banned",
    "ban_for_spam",
    "record_adult_violation",
    "is_adult_banned",
    "log_admin_action",
    "get_admin_audit",
]

