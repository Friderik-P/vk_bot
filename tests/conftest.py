# tests/conftest.py
"""Общие фикстуры для тестов."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture()
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Изолированная БД для тестов.
    Возвращает путь к файлу и инициализированное соединение.
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("VK_API_TOKEN", "test")
    monkeypatch.setenv("VK_GROUP_ID", "1")
    monkeypatch.setenv("DB_FILE", str(db_path))
    monkeypatch.setenv("ADMIN_IDS", "536284550")

    # Сбрасываем кэш конфига и пула соединений
    from src.db import connection as connection_module
    connection_module._pool = None

    from src.db import init_db
    init_db()

    return db_path


@pytest.fixture(autouse=True)
def _reset_modules(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    Сбрасываем внутреннее состояние модулей между тестами,
    чтобы тесты не влияли друг на друга.
    """
    import src.config as config_module
    from src.admins import AdminStore
    from src.db.spam import SpamTracker
    from src.chat import GigaChatService
    from src.db import connection as connection_module

    config_module._settings = None

    new_admins = AdminStore(tmp_path / "admins.yaml")
    monkeypatch.setattr("src.admins._store", new_admins, raising=False)

    new_tracker = SpamTracker()
    monkeypatch.setattr("src.db.spam._tracker", new_tracker, raising=False)

    new_chat = GigaChatService()
    monkeypatch.setattr("src.chat._service", new_chat, raising=False)

    connection_module._pool = None
    monkeypatch.setenv("VK_API_TOKEN", "test")
    monkeypatch.setenv("VK_GROUP_ID", "1")
    monkeypatch.setenv("ADMIN_IDS", "536284550")
