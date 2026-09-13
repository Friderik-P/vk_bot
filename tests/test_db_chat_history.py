# tests/test_db_chat_history.py
"""Тесты истории чата."""

from pathlib import Path

import pytest

from src.db.chat_history import save_message, load_history, clear_chat_history


class TestChatHistory:
    """Тесты модуля chat_history."""

    def test_save_and_load(self, db: Path) -> None:
        """Сохранение и загрузка сообщений."""
        save_message(user_id=1, role="user", content="привет")
        save_message(user_id=1, role="assistant", content="мяу")

        history = load_history(user_id=1, limit=10)

        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "привет"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "мяу"

    def test_load_history_limit(self, db: Path) -> None:
        """limit ограничивает количество возвращаемых сообщений."""
        for i in range(10):
            save_message(user_id=1, role="user", content=f"msg{i}")

        history = load_history(user_id=1, limit=3)

        assert len(history) == 3
        assert history[0]["content"] == "msg7"
        assert history[1]["content"] == "msg8"
        assert history[2]["content"] == "msg9"

    def test_clear_chat_history(self, db: Path) -> None:
        """clear_chat_history удаляет все сообщения пользователя."""
        save_message(user_id=1, role="user", content="привет")
        save_message(user_id=2, role="user", content="ку")

        clear_chat_history(1)

        history = load_history(user_id=1, limit=10)
        assert len(history) == 0

        history2 = load_history(user_id=2, limit=10)
        assert len(history2) == 1
