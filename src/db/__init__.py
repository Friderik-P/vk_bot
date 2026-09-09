# vk_bot/src/db/__init__.py
"""
Публичный интерфейс модуля db.
Остальные файлы используют относительные импорты, а внешний код — этот __init__.
"""

from .connection import get_connection, close_connection, close_all_connections
from .schema import init_db

# Users & blocked
from .users import (
    load_peer_ids,
    add_peer_id,
    mark_user_blocked,
    get_blocked_ids,
)

# Chat history
from .chat_history import (
    save_message,
    load_history,
    clear_chat_history,
    prune_all_history,
)

# Stats
from .stats import increment_stats, get_stats

# Spam (состояние: баны, лимиты, 18+)
from .spam import (
    check_ratelimit,
    is_spam_banned,
    ban_for_spam,
    record_adult_violation,
    is_adult_banned,
)
