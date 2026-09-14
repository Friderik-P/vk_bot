# vk_bot/src/db/__init__.py
"""
Публичный интерфейс модуля db.
Остальные файлы используют относительные импорты, а внешний код — этот __init__.
"""

from .admin_audit import get_admin_audit, log_admin_action

# История чата
from .chat_history import (
    clear_chat_history,
    load_history,
    prune_all_history,
    save_message,
)
from .connection import close_all_connections, close_connection, get_connection
from .schema import init_db

# Спам и 18+ (баны, лимиты, нарушения)
from .spam import (
    ban_for_spam,
    check_ratelimit,
    is_adult_banned,
    is_spam_banned,
    record_adult_violation,
)

# Статистика
from .stats import get_stats, increment_stats

# Пользователи и игнор-лист
from .users import (
    add_peer_id,
    get_blocked_ids,
    load_peer_ids,
    mark_user_blocked,
)

__all__ = [
    "add_peer_id",
    "ban_for_spam",
    "check_ratelimit",
    "clear_chat_history",
    "close_all_connections",
    "close_connection",
    "get_admin_audit",
    "get_blocked_ids",
    "get_connection",
    "get_stats",
    "increment_stats",
    "init_db",
    "is_adult_banned",
    "is_spam_banned",
    "load_history",
    "load_peer_ids",
    "log_admin_action",
    "mark_user_blocked",
    "prune_all_history",
    "record_adult_violation",
    "save_message",
]
