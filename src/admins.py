# vk_bot/src/admins.py
"""Хранение списка администраторов в admins.yaml."""

import logging
from pathlib import Path

import yaml

from .config import BASE_DIR, ADMIN_IDS

logger = logging.getLogger(__name__)

ADMINS_YAML = BASE_DIR / "admins.yaml"
_cached_admins: set[int] | None = None


def _load_admins() -> set[int]:
    if not ADMINS_YAML.exists():
        return set()
    with open(ADMINS_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    admins = data.get("admins", [])
    return {int(x) for x in admins if isinstance(x, int) or str(x).isdigit()}


def _save_admins(admins: set[int]) -> None:
    ADMINS_YAML.parent.mkdir(parents=True, exist_ok=True)
    with open(ADMINS_YAML, "w", encoding="utf-8") as f:
        yaml.safe_dump({"admins": sorted(admins)}, f, allow_unicode=True, sort_keys=False)


def init_admins_yaml() -> None:
    global _cached_admins
    if ADMINS_YAML.exists():
        logger.info("Файл администраторов уже существует: %s", ADMINS_YAML)
        _cached_admins = _load_admins()
        return
    admins = set(ADMIN_IDS)
    _save_admins(admins)
    _cached_admins = admins
    logger.info("Создан %s с %d администраторами", ADMINS_YAML, len(admins))


def get_admins() -> set[int]:
    global _cached_admins
    if _cached_admins is not None:
        return _cached_admins
    _cached_admins = _load_admins()
    return _cached_admins


def add_admin(user_id: int) -> bool:
    global _cached_admins
    admins = get_admins()
    if user_id in admins:
        return False
    admins.add(user_id)
    _save_admins(admins)
    _cached_admins = admins
    logger.info("Добавлен администратор user_id=%d", user_id)
    return True


def remove_admin(user_id: int) -> bool:
    global _cached_admins
    admins = get_admins()
    if user_id not in admins:
        return False
    admins.discard(user_id)
    _save_admins(admins)
    _cached_admins = admins
    logger.info("Удалён администратор user_id=%d", user_id)
    return True
