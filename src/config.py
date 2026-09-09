# vk_bot/src/config.py
"""Чтение и валидация переменных окружения из .env."""

import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Загружаем .env из корня проекта (папка, где лежит main.py)
BASE_DIR = Path(__file__).resolve().parent.parent


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


@dataclass(frozen=True)
class Settings:
    """Централизованная конфигурация приложения."""

    base_dir: Path
    vk_api_token: str
    vk_group_id: int
    gigachat_auth_key: str | None
    db_file: str
    log_dir: str
    server_name: str
    max_history_per_user: int
    max_message_length: int
    spam_ban_minutes: int
    adult_ban_minutes: int
    adult_violation_limit: int
    adult_violation_window_minutes: int
    gigachat_timeout_seconds: int
    max_history: int
    rate_limit_count: int
    rate_limit_minutes: int
    admin_ids: tuple[int, ...]

    @classmethod
    def load(cls) -> "Settings":
        """Загружает и валидирует конфигурацию."""
        vk_api_token = _get_required("VK_API_TOKEN")
        vk_group_id = _get_int("VK_GROUP_ID", 0)
        if vk_group_id <= 0:
            raise RuntimeError("VK_GROUP_ID не задан или некорректен (должен быть положительным) — проверьте .env")

        gigachat_auth_key = os.getenv("GIGACHAT_AUTH_KEY")
        if not gigachat_auth_key:
            logger.warning("GIGACHAT_AUTH_KEY не задан — LLM-диалог будет недоступен.")

        raw_admins = os.getenv("ADMIN_IDS", "")
        admin_ids: list[int] = []
        for part in raw_admins.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                admin_ids.append(int(part))
            except ValueError:
                logger.warning("ADMIN_IDS: пропущено некорректное значение %s", part)
        if not admin_ids:
            logger.warning("ADMIN_IDS не задан — команды администратора недоступны.")
        else:
            logger.info("Загружено администраторов: %d", len(admin_ids))

        db_file = str((BASE_DIR / os.getenv("DB_FILE", "bot.db")).resolve())
        log_dir = str((BASE_DIR / os.getenv("LOG_DIR", "logs")).resolve())
        server_name = os.getenv("SERVER_NAME", "MyVKBot")

        return cls(
            base_dir=BASE_DIR,
            vk_api_token=vk_api_token,
            vk_group_id=vk_group_id,
            gigachat_auth_key=gigachat_auth_key,
            db_file=db_file,
            log_dir=log_dir,
            server_name=server_name,
            max_history_per_user=_get_int_min("MAX_HISTORY_PER_USER", 500, min_value=1),
            max_message_length=_get_int_min("MAX_MESSAGE_LENGTH", 2000, min_value=1),
            spam_ban_minutes=_get_int_min("SPAM_BAN_MINUTES", 5, min_value=1),
            adult_ban_minutes=_get_int_min("ADULT_BAN_MINUTES", 5, min_value=1),
            adult_violation_limit=_get_int_min("ADULT_VIOLATION_LIMIT", 3, min_value=1),
            adult_violation_window_minutes=_get_int_min("ADULT_VIOLATION_WINDOW_MINUTES", 30, min_value=1),
            gigachat_timeout_seconds=_get_int_min("GIGACHAT_TIMEOUT_SECONDS", 15, min_value=1),
            max_history=_get_int_min("MAX_HISTORY", 50, min_value=1),
            rate_limit_count=_get_int_min("RATE_LIMIT_COUNT", 20, min_value=1),
            rate_limit_minutes=_get_int_min("RATE_LIMIT_MINUTES", 5, min_value=1),
            admin_ids=tuple(admin_ids),
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Возвращает загруженный экземпляр конфигурации (ленивая загрузка)."""
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


class _SettingsProxy:
    """Прокси для ленивой загрузки конфигурации без побочных эффектов при импорте."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_settings(), name)

    def __repr__(self) -> str:
        return repr(get_settings())


settings = _SettingsProxy()

__all__ = ["Settings", "settings", "BASE_DIR", "load", "get_settings"]
