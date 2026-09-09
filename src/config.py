# vk_bot/src/config.py
"""Чтение и валидация переменных окружения из .env."""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Загружаем .env из корня проекта (папка, где лежит main.py)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _get_required(name: str) -> str:
    """Возвращает значение обязательной переменной или бросает RuntimeError."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} не найден в .env — добавьте его и перезапустите.")
    return value


def _get_int(name: str, default: int) -> int:
    """Возвращает int-значение или default, если переменная не задана."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("%s должен быть числом, используется default=%d", name, default)
        return default


def _get_int_min(name: str, default: int, min_value: int) -> int:
    """Возвращает int-значение >= min_value, иначе default."""
    value = _get_int(name, default)
    if value < min_value:
        logger.warning(
            "%s=%d слишком мал (минимум %d), используется default=%d",
            name, value, min_value, default,
        )
        return default
    return value


# --- VK API ---
VK_API_TOKEN = _get_required("VK_API_TOKEN")
VK_GROUP_ID = _get_int("VK_GROUP_ID", 0)
if VK_GROUP_ID <= 0:
    raise RuntimeError("VK_GROUP_ID не задан или некорректен (должен быть положительным) — проверьте .env")

# --- GigaChat ---
GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")
if not GIGACHAT_AUTH_KEY:
    logger.warning("GIGACHAT_AUTH_KEY не задан — LLM-диалог будет недоступен.")

# --- Администраторы ---
raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = []
for part in raw_admins.split(","):
    part = part.strip()
    if not part:
        continue
    try:
        ADMIN_IDS.append(int(part))
    except ValueError:
        logger.warning("ADMIN_IDS: пропущено некорректное значение %s", part)

if not ADMIN_IDS:
    logger.warning("ADMIN_IDS не задан — команды администратора недоступны.")
else:
    logger.info("Загружено администраторов: %d", len(ADMIN_IDS))

# --- База данных и логи ---
DB_FILE = str((BASE_DIR / os.getenv("DB_FILE", "bot.db")).resolve())
LOG_DIR = str((BASE_DIR / os.getenv("LOG_DIR", "logs")).resolve())
SERVER_NAME = os.getenv("SERVER_NAME", "MyVKBot")

# --- Ограничения и таймауты ---
MAX_HISTORY_PER_USER = _get_int_min("MAX_HISTORY_PER_USER", 500, min_value=1)
MAX_MESSAGE_LENGTH = _get_int_min("MAX_MESSAGE_LENGTH", 2000, min_value=1)
SPAM_BAN_MINUTES = _get_int_min("SPAM_BAN_MINUTES", 5, min_value=1)
ADULT_BAN_MINUTES = _get_int_min("ADULT_BAN_MINUTES", 5, min_value=1)
ADULT_VIOLATION_LIMIT = _get_int_min("ADULT_VIOLATION_LIMIT", 3, min_value=1)
ADULT_VIOLATION_WINDOW_MINUTES = _get_int_min("ADULT_VIOLATION_WINDOW_MINUTES", 30, min_value=1)
GIGACHAT_TIMEOUT_SECONDS = _get_int_min("GIGACHAT_TIMEOUT_SECONDS", 15, min_value=1)

# --- Опциональные настройки (имеют дефолты) ---
MAX_HISTORY = _get_int_min("MAX_HISTORY", 50, min_value=1)
RATE_LIMIT_COUNT = _get_int_min("RATE_LIMIT_COUNT", 20, min_value=1)
RATE_LIMIT_MINUTES = _get_int_min("RATE_LIMIT_MINUTES", 5, min_value=1)

# --- Итоговый лог при загрузке ---
logger.info(
    "Конфигурация загружена: group_id=%d, db=%s, logs=%s, llm=%s, admins=%d, "
    "max_history=%d, rate_limit=%d/%dmin, server=%s, "
    "max_history_per_user=%d, max_message_length=%d, "
    "spam_ban=%dmin, adult_ban=%dmin, adult_limit=%d/%dmin, gigachat_timeout=%dsec",
    VK_GROUP_ID,
    DB_FILE,
    LOG_DIR,
    "включён" if GIGACHAT_AUTH_KEY else "выключен",
    len(ADMIN_IDS),
    MAX_HISTORY,
    RATE_LIMIT_COUNT,
    RATE_LIMIT_MINUTES,
    SERVER_NAME,
    MAX_HISTORY_PER_USER,
    MAX_MESSAGE_LENGTH,
    SPAM_BAN_MINUTES,
    ADULT_BAN_MINUTES,
    ADULT_VIOLATION_LIMIT,
    ADULT_VIOLATION_WINDOW_MINUTES,
    GIGACHAT_TIMEOUT_SECONDS,
)
