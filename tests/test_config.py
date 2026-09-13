# tests/test_config.py
"""Тесты конфигурации: Settings.load(), валидация, __repr__."""

import os
from pathlib import Path

import pytest

from src.config import Settings, BASE_DIR


class TestSettings:
    """Тесты Settings.load()."""

    def test_load_from_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Settings загружается из переменных окружения."""
        monkeypatch.setenv("VK_API_TOKEN", "test_token")
        monkeypatch.setenv("VK_GROUP_ID", "123")
        monkeypatch.setenv("DB_FILE", str(tmp_path / "test.db"))
        monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
        monkeypatch.setenv("SERVER_NAME", "TestServer")
        monkeypatch.setenv("MAX_HISTORY_PER_USER", "100")
        monkeypatch.setenv("MAX_MESSAGE_LENGTH", "500")
        monkeypatch.setenv("SPAM_BAN_MINUTES", "10")
        monkeypatch.setenv("ADULT_BAN_MINUTES", "15")
        monkeypatch.setenv("ADULT_VIOLATION_LIMIT", "5")
        monkeypatch.setenv("ADULT_VIOLATION_WINDOW_MINUTES", "60")
        monkeypatch.setenv("GIGACHAT_TIMEOUT_SECONDS", "20")
        monkeypatch.setenv("MAX_HISTORY", "30")
        monkeypatch.setenv("RATE_LIMIT_COUNT", "50")
        monkeypatch.setenv("RATE_LIMIT_MINUTES", "10")
        monkeypatch.setenv("ADMIN_IDS", "1,2,3")

        settings = Settings.load()

        assert settings.vk_api_token == "test_token"
        assert settings.vk_group_id == 123
        assert settings.server_name == "TestServer"
        assert settings.max_history_per_user == 100
        assert settings.admin_ids == (1, 2, 3)
        assert settings.base_dir == BASE_DIR

    def test_missing_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """При отсутствии VK_API_TOKEN выбрасывается RuntimeError."""
        monkeypatch.delenv("VK_API_TOKEN", raising=False)
        with pytest.raises(RuntimeError, match="VK_API_TOKEN не найден"):
            Settings.load()

    def test_invalid_group_id_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """При VK_GROUP_ID <= 0 выбрасывается RuntimeError."""
        monkeypatch.setenv("VK_API_TOKEN", "test")
        monkeypatch.setenv("VK_GROUP_ID", "0")
        with pytest.raises(RuntimeError, match="VK_GROUP_ID"):
            Settings.load()

    def test_defaults_applied(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Проверяем, что дефолты применяются при отсутствии опциональных переменных."""
        monkeypatch.setenv("VK_API_TOKEN", "test")
        monkeypatch.setenv("VK_GROUP_ID", "123")
        monkeypatch.setenv("DB_FILE", str(tmp_path / "test.db"))
        monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
        monkeypatch.setenv("ADMIN_IDS", "")

        settings = Settings.load()

        assert settings.server_name == "MyVKBot"
        assert settings.max_history_per_user == 500
        assert settings.spam_ban_minutes == 5
        assert settings.adult_ban_minutes == 5
        assert settings.adult_violation_limit == 3
        assert settings.gigachat_timeout_seconds == 15
        assert settings.max_history == 50
        assert settings.rate_limit_count == 20
        assert settings.rate_limit_minutes == 5
        assert settings.admin_ids == ()

    def test_repr_does_not_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """__repr__ не должен падать при корректном конфиге."""
        monkeypatch.setenv("VK_API_TOKEN", "test")
        monkeypatch.setenv("VK_GROUP_ID", "123")
        monkeypatch.setenv("ADMIN_IDS", "536284550")

        settings = Settings.load()
        r = repr(settings)
        assert "Settings" in r
        assert "vk_group_id=123" in r
