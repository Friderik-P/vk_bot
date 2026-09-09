# tests/test_handlers_message.py
"""Базовые тесты обработчика сообщений."""

import pytest

from src.handlers.message import handle_message, SIMPLE_TRIGGERS
from src.prompts import MEOW_RESPONSE, HELP_RESPONSE, RESET_RESPONSE


class TestHandleMessage:
    """Тесты handle_message."""

    def test_returns_true_for_event_without_message(self) -> None:
        """Событие без message обрабатывается как True (пропущено)."""
        event = type("Event", (), {"message": None})()
        server = type("Server", (), {"send_message": lambda *a, **k: None})()
        assert handle_message(server, event) is True

    def test_meow_command(self) -> None:
        """Команда 'мяу' возвращает ответ."""
        sent = []
        class MockServer:
            def send_message(self, peer_id, message, keyboard=None):
                sent.append(message)
        server = MockServer()
        event = type("Event", (), {"message": type("Msg", (), {"text": "мяу", "peer_id": 1, "from_id": 1})()})()

        result = handle_message(server, event)

        assert result is True
        assert sent == [MEOW_RESPONSE]

    def test_help_command(self) -> None:
        """Команда 'помощь' возвращает HELP_RESPONSE."""
        sent = []
        class MockServer:
            def send_message(self, peer_id, message, keyboard=None):
                sent.append(message)
        server = MockServer()
        event = type("Event", (), {"message": type("Msg", (), {"text": "помощь", "peer_id": 1, "from_id": 1})()})()

        result = handle_message(server, event)

        assert result is True
        assert sent == [HELP_RESPONSE]

    def test_simple_triggers(self) -> None:
        """Простые триггеры возвращают ответ."""
        for trigger in ["привет", "пока", "спасибо"]:
            sent = []
            class MockServer:
                def send_message(self, peer_id, message, keyboard=None):
                    sent.append(message)
            server = MockServer()
            event = type("Event", (), {"message": type("Msg", (), {"text": trigger, "peer_id": 1, "from_id": 1})()})()

            result = handle_message(server, event)

            assert result is True
            assert len(sent) == 1

    def test_empty_text(self) -> None:
        """Пустой текст возвращает True (обработано)."""
        sent = []
        class MockServer:
            def send_message(self, *args, **kwargs):
                sent.append("called")
        server = MockServer()
        event = type("Event", (), {"message": type("Msg", (), {"text": "", "peer_id": 1, "from_id": 1})()})()

        result = handle_message(server, event)

        assert result is True
        assert sent == []


class TestSimpleTriggers:
    """Тесты SIMPLE_TRIGGERS."""

    def test_triggers_exist(self) -> None:
        """SIMPLE_TRIGGERS не пустой."""
        assert len(SIMPLE_TRIGGERS) > 0

    def test_common_triggers_present(self) -> None:
        """Основные триггеры присутствуют."""
        assert "привет" in SIMPLE_TRIGGERS
        assert "пока" in SIMPLE_TRIGGERS
        assert "спасибо" in SIMPLE_TRIGGERS
