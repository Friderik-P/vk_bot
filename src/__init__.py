# vk_bot/src/__init__.py
"""
VK Bot with GigaChat — основной пакет проекта.

Содержит все модули бота: сервер, обработчики, фильтры,
работу с БД, планировщик и обёртки над внешними API.

Импорты можно делать двумя способами:
    # Рекомендуемый (явный)
    from src.config import VK_API_TOKEN
    from src.db import init_db, save_message
    from src.server import Server

    # Либо через этот __init__.py (если нужны часто используемые символы)
    from src import VK_API_TOKEN, init_db, Server
"""

# --- Часто используемые конфиги ---
from .config import VK_API_TOKEN, VK_GROUP_ID
from .admins import get_admins, add_admin

# --- Инициализация и управление БД ---
from .db import init_db, close_all_connections

# --- Сервер и запуск ---
from .server import Server

# --- Статистика и антиспам ---
from .db import increment_stats, get_stats
from .db import (
    check_ratelimit,
    is_spam_banned,
    ban_for_spam,
    record_adult_violation,
    is_adult_banned,
)
