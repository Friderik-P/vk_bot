# vk_bot/src/admins.py
"""Хранение списка администраторов в admins.yaml."""

import logging
from pathlib import Path

import yaml

from .config import settings

logger = logging.getLogger(__name__)


class AdminStore:
    """Хранилище администраторов с кэшированием и синхронизацией с YAML."""

    def __init__(self, yaml_path: Path) -> None:
        self._yaml_path = yaml_path
        self._cached: set[int] = set()

    def _load(self) -> set[int]:
        if not self._yaml_path.exists():
            return set()
        with open(self._yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        admins = data.get("admins", [])
        return {int(x) for x in admins if isinstance(x, int) or str(x).isdigit()}

    def _save(self, admins: set[int]) -> None:
        self._yaml_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"admins": sorted(admins)}, f, allow_unicode=True, sort_keys=False)

    def init(self, env_admins: tuple[int, ...]) -> None:
        """Инициализирует хранилище из .env, если файл отсутствует или пуст."""
        if self._yaml_path.exists():
            loaded = self._load()
            if loaded:
                self._cached = loaded
                logger.info("Файл администраторов загружен: %s (%d шт.)", self._yaml_path, len(loaded))
                return
            logger.warning("Файл администраторов пуст или не содержит валидных ID — пересоздаю из .env")

        if not env_admins:
            logger.warning("ADMIN_IDS не задан в .env — admins.yaml не создан")
            self._cached = set()
            return

        self._save(set(env_admins))
        self._cached = set(env_admins)
        logger.info("Создан %s с %d администраторами из .env", self._yaml_path, len(env_admins))

    def get_all(self) -> set[int]:
        """Возвращает копию текущего списка администраторов."""
        return set(self._cached)

    def add(self, user_id: int) -> bool:
        """Добавляет администратора. Возвращает True, если добавлен."""
        if user_id in self._cached:
            return False
        self._cached.add(user_id)
        self._save(self._cached)
        logger.info("Добавлен администратор user_id=%d", user_id)
        return True

    def remove(self, user_id: int) -> bool:
        """Удаляет администратора. Возвращает True, если удалён."""
        if user_id not in self._cached:
            return False
        self._cached.discard(user_id)
        self._save(self._cached)
        logger.info("Удалён администратор user_id=%d", user_id)
        return True


_store = AdminStore(settings.base_dir / "admins.yaml")


def init_admins_yaml() -> None:
    _store.init(settings.admin_ids)


def get_admins() -> set[int]:
    return _store.get_all()


def add_admin(user_id: int) -> bool:
    return _store.add(user_id)


def remove_admin(user_id: int) -> bool:
    return _store.remove(user_id)


__all__ = ["AdminStore", "init_admins_yaml", "get_admins", "add_admin", "remove_admin"]
