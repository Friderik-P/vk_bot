# tests/test_db_spam.py
"""Тесты антиспам-трекера SpamTracker."""

from datetime import datetime, timedelta

import pytest

from src.db.spam import SpamTracker


class TestSpamTracker:
    """Тесты класса SpamTracker."""

    def test_check_ratelimit_allows_first_message(self) -> None:
        """Первое сообщение всегда проходит."""
        tracker = SpamTracker()
        assert tracker.check_ratelimit(1, max_msgs=2, window_minutes=1) is True

    def test_check_ratelimit_blocks_after_limit(self) -> None:
        """После превышения лимита сообщений пользователь банится."""
        tracker = SpamTracker()

        for _ in range(3):
            assert tracker.check_ratelimit(1, max_msgs=3, window_minutes=1) is True

        # 4-е сообщение должно быть заблокировано
        assert tracker.check_ratelimit(1, max_msgs=3, window_minutes=1) is False
        assert tracker.is_spam_banned(1) is True

    def test_ratelimit_window_expires(self) -> None:
        """Сообщения старше окна не учитываются."""
        tracker = SpamTracker()
        now = datetime.now()

        # Имитируем 3 сообщения 2 минуты назад
        old_time = now - timedelta(minutes=2)
        with tracker._lock:
            for _ in range(3):
                tracker._ratelimit_data[1].append(old_time)

        # Окно 1 минута — старые сообщения не должны считаться
        assert tracker.check_ratelimit(1, max_msgs=2, window_minutes=1) is True
        assert tracker.is_spam_banned(1) is False

    def test_ban_for_spam(self) -> None:
        """Принудительный бан за спам."""
        tracker = SpamTracker()
        tracker.ban_for_spam(1, minutes=5)
        assert tracker.is_spam_banned(1) is True

    def test_spam_ban_expires(self) -> None:
        """Бан истекает после указанного времени."""
        tracker = SpamTracker()
        # Баним на отрицательное время, чтобы бан сразу истёк
        tracker.ban_for_spam(1, minutes=-1)
        assert tracker.is_spam_banned(1) is False

    def test_record_adult_violation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """18+ нарушения считаются, бан наступает после лимита."""
        monkeypatch.setattr("src.db.spam.settings.adult_violation_limit", 3)
        monkeypatch.setattr("src.db.spam.settings.adult_violation_window_minutes", 60)
        monkeypatch.setattr("src.db.spam.settings.adult_ban_minutes", 5)

        tracker = SpamTracker()

        for _ in range(2):
            assert tracker.record_adult_violation(1) is False

        # 3-е нарушение должно дать бан
        assert tracker.record_adult_violation(1) is True
        assert tracker.is_adult_banned(1) is True

    def test_adult_violations_clear_after_ban_expires(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """После истечения бана 18+ счётчик нарушений сбрасывается."""
        monkeypatch.setattr("src.db.spam.settings.adult_violation_limit", 2)
        monkeypatch.setattr("src.db.spam.settings.adult_violation_window_minutes", 60)
        monkeypatch.setattr("src.db.spam.settings.adult_ban_minutes", 5)

        tracker = SpamTracker()
        tracker.record_adult_violation(1)
        tracker.record_adult_violation(1)
        assert tracker.is_adult_banned(1) is True

        # Имитируем истечение бана
        with tracker._lock:
            tracker._adult_bans[1] = datetime.now() - timedelta(minutes=1)

        assert tracker.is_adult_banned(1) is False

    def test_concurrent_access(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Проверка потокобезопасности (стресс-тест)."""
        import threading

        monkeypatch.setattr("src.db.spam.settings.spam_ban_minutes", 5)
        monkeypatch.setattr("src.db.spam.settings.adult_violation_limit", 10)
        monkeypatch.setattr("src.db.spam.settings.adult_violation_window_minutes", 60)
        monkeypatch.setattr("src.db.spam.settings.adult_ban_minutes", 5)

        tracker = SpamTracker()
        errors = []

        def worker(uid: int) -> None:
            try:
                for _ in range(50):
                    tracker.check_ratelimit(uid, max_msgs=100, window_minutes=5)
                    tracker.record_adult_violation(uid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent errors: {errors}"


class TestBackwardCompatibleFunctions:
    """Тесты функций-обёрток в модуле spam."""

    def test_module_functions_delegate(self) -> None:
        """Функции модуля делегируют SpamTracker."""
        from src.db import spam as spam_module

        assert spam_module.check_ratelimit is not spam_module.SpamTracker.check_ratelimit
        # Вызов без ошибок — значит делегирование работает
        assert spam_module.check_ratelimit(999, max_msgs=10, window_minutes=1) is True
