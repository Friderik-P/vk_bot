# tests/test_db_users.py
"""Тесты работы с пользователями в БД."""

from pathlib import Path

import pytest

from src.db.users import (
    load_peer_ids,
    add_peer_id,
    mark_user_blocked,
    get_blocked_ids,
)


class TestUsers:
    """Тесты модуля users."""

    def test_add_and_load_peer_id(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Добавление пользователя и загрузка из БД."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("VK_API_TOKEN", "test")
        monkeypatch.setenv("VK_GROUP_ID", "1")
        monkeypatch.setenv("DB_FILE", str(db_path))

        from src.db import init_db
        init_db()

        add_peer_id(set(), 123)
        peer_ids = load_peer_ids()

        assert 123 in peer_ids

    def test_load_returns_set(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_peer_ids() возвращает set."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("VK_API_TOKEN", "test")
        monkeypatch.setenv("VK_GROUP_ID", "1")
        monkeypatch.setenv("DB_FILE", str(db_path))

        from src.db import init_db
        init_db()

        result = load_peer_ids()
        assert isinstance(result, set)

    def test_mark_user_blocked(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """mark_user_blocked() добавляет пользователя в blocked_users."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("VK_API_TOKEN", "test")
        monkeypatch.setenv("VK_GROUP_ID", "1")
        monkeypatch.setenv("DB_FILE", str(db_path))

        from src.db import init_db
        init_db()

        mark_user_blocked(999, reason="test ban")
        blocked = get_blocked_ids()

        assert 999 in blocked
