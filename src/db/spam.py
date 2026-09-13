# vk_bot/src/db/spam.py
"""
Антиспам-логика: лимиты сообщений, баны, счётчик нарушений 18+.
Вся логика — в памяти (не сохраняется в БД).
Текстовый анализ спама — в filters/spam.py.
"""

from datetime import datetime, timedelta
from collections import defaultdict, deque

import logging
import threading

from ..config import settings
from ..constants import SPAM_CLEANUP_INTERVAL_SECONDS, SPAM_RATELIMIT_MAXLEN, SPAM_ADULT_VIOLATION_MAXLEN

logger = logging.getLogger(__name__)


class SpamTracker:
    """Потокобезопасный трекер спама и 18+ нарушений."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ratelimit_data: dict[int, deque] = defaultdict(lambda: deque(maxlen=SPAM_RATELIMIT_MAXLEN))
        self._spam_bans: dict[int, datetime] = {}
        self._adult_bans: dict[int, datetime] = {}
        self._adult_violations: dict[int, deque] = defaultdict(lambda: deque(maxlen=SPAM_ADULT_VIOLATION_MAXLEN))
        self._cleanup_interval = SPAM_CLEANUP_INTERVAL_SECONDS
        self._last_cleanup = datetime.now()

    def _maybe_cleanup(self) -> None:
        """Периодически очищает истёкшие баны и пустые deque'ы."""
        now = datetime.now()
        if (now - self._last_cleanup).total_seconds() < self._cleanup_interval:
            return
        self._last_cleanup = now

        expired_spam = [uid for uid, exp in self._spam_bans.items() if exp <= now]
        for uid in expired_spam:
            del self._spam_bans[uid]

        expired_adult = [uid for uid, exp in self._adult_bans.items() if exp <= now]
        for uid in expired_adult:
            del self._adult_bans[uid]
            if uid in self._adult_violations:
                self._adult_violations[uid].clear()

        empty_rl = [uid for uid, dq in self._ratelimit_data.items() if not dq]
        for uid in empty_rl:
            del self._ratelimit_data[uid]

        empty_av = [uid for uid, dq in self._adult_violations.items() if not dq]
        for uid in empty_av:
            del self._adult_violations[uid]

        if expired_spam or expired_adult or empty_rl or empty_av:
            logger.debug(
                "Очистка spam-данных: удалено банов спам=%d, 18+=%d, "
                "пустых записей ratelimit=%d, adult=%d",
                len(expired_spam), len(expired_adult),
                len(empty_rl), len(empty_av),
            )

    def check_ratelimit(self, user_id: int, max_msgs: int = 20, window_minutes: int = 5) -> bool:
        """Проверяет лимит сообщений в скользящем окне."""
        now = datetime.now()

        with self._lock:
            self._maybe_cleanup()

            times = self._ratelimit_data[user_id]

            while times and times[0] < now - timedelta(minutes=window_minutes):
                times.popleft()

            if len(times) >= max_msgs:
                self._spam_bans[user_id] = now + timedelta(minutes=settings.spam_ban_minutes)
                logger.warning(
                    "Пользователь %d превысил лимит сообщений — бан на %d мин",
                    user_id, settings.spam_ban_minutes,
                )
                return False

            times.append(now)
            return True

    def is_spam_banned(self, user_id: int) -> bool:
        """Проверяет, находится ли пользователь в бане за спам."""
        with self._lock:
            ban_exp = self._spam_bans.get(user_id)
            if ban_exp is None:
                return False
            if ban_exp > datetime.now():
                return True
            del self._spam_bans[user_id]
            if user_id in self._ratelimit_data:
                self._ratelimit_data[user_id].clear()
            return False

    def ban_for_spam(self, user_id: int, minutes: int = settings.spam_ban_minutes) -> None:
        """Принудительно банит пользователя за спам на указанное время."""
        with self._lock:
            self._maybe_cleanup()
            self._spam_bans[user_id] = datetime.now() + timedelta(minutes=minutes)
            logger.info(
                "Пользователь %d принудительно забанен за спам на %d мин",
                user_id, minutes,
            )

    def record_adult_violation(self, user_id: int) -> bool:
        """
        Фиксирует нарушение 18+ для пользователя.
        Возвращает True, если пользователь получил бан (превышен лимит).
        """
        now = datetime.now()

        with self._lock:
            self._maybe_cleanup()

            times = self._adult_violations[user_id]

            while times and times[0] < now - timedelta(minutes=settings.adult_violation_window_minutes):
                times.popleft()

            times.append(now)

            if len(times) >= settings.adult_violation_limit:
                self._adult_bans[user_id] = now + timedelta(minutes=settings.adult_ban_minutes)
                logger.warning(
                    "Пользователь %d забанен на %d мин за 18+ контент (нарушений: %d)",
                    user_id, settings.adult_ban_minutes, len(times),
                )
                return True

            logger.info(
                "18+ нарушение #%d для пользователя %d (бан при %d)",
                len(times), user_id, settings.adult_violation_limit,
            )
            return False

    def is_adult_banned(self, user_id: int) -> bool:
        """Проверяет, находится ли пользователь в бане за 18+ контент."""
        with self._lock:
            ban_exp = self._adult_bans.get(user_id)
            if ban_exp is None:
                return False
            if ban_exp > datetime.now():
                return True
            del self._adult_bans[user_id]
            if user_id in self._adult_violations:
                self._adult_violations[user_id].clear()
            logger.info("Бан 18+ для пользователя %d истёк — очищен счётчик", user_id)
            return False


_tracker = SpamTracker()


def check_ratelimit(user_id: int, max_msgs: int = 20, window_minutes: int = 5) -> bool:
    return _tracker.check_ratelimit(user_id, max_msgs, window_minutes)


def is_spam_banned(user_id: int) -> bool:
    return _tracker.is_spam_banned(user_id)


def ban_for_spam(user_id: int, minutes: int = settings.spam_ban_minutes) -> None:
    _tracker.ban_for_spam(user_id, minutes)


def record_adult_violation(user_id: int) -> bool:
    return _tracker.record_adult_violation(user_id)


def is_adult_banned(user_id: int) -> bool:
    return _tracker.is_adult_banned(user_id)


__all__ = [
    "SpamTracker",
    "check_ratelimit",
    "is_spam_banned",
    "ban_for_spam",
    "record_adult_violation",
    "is_adult_banned",
]
