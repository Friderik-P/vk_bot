# vk_bot/src/db/spam.py
"""
Антиспам-логика: лимиты сообщений, баны, счётчик нарушений 18+.
Баны и нарушения 18+ сохраняются в БД (персистентны между рестартами).
Текстовый анализ спама — в filters/spam.py.
"""

from datetime import datetime, timedelta
from collections import defaultdict, deque

import logging
import sqlite3
import threading

from ..config import settings
from ..constants import SPAM_CLEANUP_INTERVAL_SECONDS, SPAM_RATELIMIT_MAXLEN, SPAM_ADULT_VIOLATION_MAXLEN
from .connection import get_connection, retry_on_lock

logger = logging.getLogger(__name__)


class SpamTracker:
    """Потокобезопасный трекер спама и 18+ нарушений с персистентностью в БД."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._ratelimit_data: dict[int, deque] = defaultdict(lambda: deque(maxlen=SPAM_RATELIMIT_MAXLEN))
        self._spam_bans: dict[int, datetime] = {}
        self._adult_bans: dict[int, datetime] = {}
        self._adult_violations: dict[int, deque] = defaultdict(lambda: deque(maxlen=SPAM_ADULT_VIOLATION_MAXLEN))
        self._cleanup_interval = SPAM_CLEANUP_INTERVAL_SECONDS
        self._last_cleanup = datetime.now()
        self._db_loaded = False

    def _ensure_db_loaded(self) -> None:
        """Ленивая загрузка банов из БД при первом обращении."""
        if self._db_loaded:
            return
        with self._lock:
            if self._db_loaded:
                return
            self._load_from_db()
            self._db_loaded = True

    def _load_from_db(self) -> None:
        """Загружает активные баны и нарушения из БД при старте."""
        now = datetime.now()

        def _load():
            with get_connection() as conn:
                # Spam bans
                cur = conn.execute("SELECT user_id, expires_at FROM spam_bans WHERE expires_at > ?", (now.isoformat(),))
                for row in cur.fetchall():
                    self._spam_bans[row["user_id"]] = datetime.fromisoformat(row["expires_at"])

                # Adult bans
                cur = conn.execute(
                    "SELECT user_id, expires_at, violation_count FROM adult_bans WHERE expires_at > ?",
                    (now.isoformat(),),
                )
                for row in cur.fetchall():
                    self._adult_bans[row["user_id"]] = datetime.fromisoformat(row["expires_at"])
                    # Load recent violations for this user within the window
                    window_start = now - timedelta(minutes=settings.adult_violation_window_minutes)
                    cur2 = conn.execute(
                        "SELECT created_at FROM adult_violations WHERE user_id = ? AND created_at > ?",
                        (row["user_id"], window_start.isoformat()),
                    )
                    for vrow in cur2.fetchall():
                        self._adult_violations[row["user_id"]].append(datetime.fromisoformat(vrow["created_at"]))

        try:
            retry_on_lock(_load)
            logger.debug("Загружены баны из БД: spam=%d, adult=%d", len(self._spam_bans), len(self._adult_bans))
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                logger.debug("Таблицы банов ещё не созданы — пропускаю загрузку")
            else:
                logger.exception("Ошибка загрузки банов из БД: %s", e)
        except Exception as e:
            logger.exception("Ошибка загрузки банов из БД: %s", e)

    def _save_spam_ban(self, user_id: int, expires_at: datetime) -> None:
        def _save():
            with get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO spam_bans (user_id, banned_at, expires_at) VALUES (?, datetime('now'), ?)",
                    (user_id, expires_at.isoformat()),
                )
                conn.commit()

        try:
            retry_on_lock(_save)
        except Exception as e:
            logger.exception("Ошибка сохранения спам-бана в БД: %s", e)

    def _remove_spam_ban(self, user_id: int) -> None:
        def _remove():
            with get_connection() as conn:
                conn.execute("DELETE FROM spam_bans WHERE user_id = ?", (user_id,))
                conn.commit()

        try:
            retry_on_lock(_remove)
        except Exception as e:
            logger.exception("Ошибка удаления спам-бана из БД: %s", e)

    def _save_adult_ban(self, user_id: int, expires_at: datetime, violation_count: int) -> None:
        def _save():
            with get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO adult_bans "
                    "(user_id, banned_at, expires_at, violation_count) "
                    "VALUES (?, datetime('now'), ?, ?)",
                    (user_id, expires_at.isoformat(), violation_count),
                )
                conn.commit()

        try:
            retry_on_lock(_save)
        except Exception as e:
            logger.exception("Ошибка сохранения 18+ бана в БД: %s", e)

    def _remove_adult_ban(self, user_id: int) -> None:
        def _remove():
            with get_connection() as conn:
                conn.execute("DELETE FROM adult_bans WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM adult_violations WHERE user_id = ?", (user_id,))
                conn.commit()

        try:
            retry_on_lock(_remove)
        except Exception as e:
            logger.exception("Ошибка удаления 18+ бана из БД: %s", e)

    def _save_adult_violation(self, user_id: int, created_at: datetime) -> None:
        def _save():
            with get_connection() as conn:
                conn.execute(
                    "INSERT INTO adult_violations (user_id, created_at) VALUES (?, ?)",
                    (user_id, created_at.isoformat()),
                )
                conn.commit()

        try:
            retry_on_lock(_save)
        except Exception as e:
            logger.exception("Ошибка сохранения 18+ нарушения в БД: %s", e)

    def _cleanup_old_violations(self, user_id: int, window_start: datetime) -> None:
        def _clean():
            with get_connection() as conn:
                conn.execute(
                    "DELETE FROM adult_violations WHERE user_id = ? AND created_at < ?",
                    (user_id, window_start.isoformat()),
                )
                conn.commit()

        try:
            retry_on_lock(_clean)
        except Exception as e:
            logger.exception("Ошибка очистки старых нарушений из БД: %s", e)

    def _maybe_cleanup(self) -> None:
        """Периодически очищает истёкшие баны и пустые deque'и."""
        self._ensure_db_loaded()
        now = datetime.now()
        if (now - self._last_cleanup).total_seconds() < self._cleanup_interval:
            return
        self._last_cleanup = now

        expired_spam = [uid for uid, exp in self._spam_bans.items() if exp <= now]
        for uid in expired_spam:
            del self._spam_bans[uid]
            self._remove_spam_ban(uid)

        expired_adult = [uid for uid, exp in self._adult_bans.items() if exp <= now]
        for uid in expired_adult:
            del self._adult_bans[uid]
            if uid in self._adult_violations:
                self._adult_violations[uid].clear()
            self._remove_adult_ban(uid)

        empty_rl = [uid for uid, dq in self._ratelimit_data.items() if not dq]
        for uid in empty_rl:
            del self._ratelimit_data[uid]

        empty_av = [uid for uid, dq in self._adult_violations.items() if not dq]
        for uid in empty_av:
            del self._adult_violations[uid]

        if expired_spam or expired_adult or empty_rl or empty_av:
            logger.debug(
                "Очистка spam-данных: удалено банов спам=%d, 18+=%d, " "пустых записей ratelimit=%d, adult=%d",
                len(expired_spam),
                len(expired_adult),
                len(empty_rl),
                len(empty_av),
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
                expires = now + timedelta(minutes=settings.spam_ban_minutes)
                self._spam_bans[user_id] = expires
                self._save_spam_ban(user_id, expires)
                logger.warning(
                    "Пользователь %d превысил лимит сообщений — бан на %d мин",
                    user_id,
                    settings.spam_ban_minutes,
                )
                return False

            times.append(now)
            return True

    def is_spam_banned(self, user_id: int) -> bool:
        """Проверяет, находится ли пользователь в бане за спам."""
        self._ensure_db_loaded()
        with self._lock:
            ban_exp = self._spam_bans.get(user_id)
            if ban_exp is None:
                return False
            if ban_exp > datetime.now():
                return True
            del self._spam_bans[user_id]
            self._remove_spam_ban(user_id)
            if user_id in self._ratelimit_data:
                self._ratelimit_data[user_id].clear()
            return False

    def ban_for_spam(self, user_id: int, minutes: int | None = None) -> None:
        """Принудительно банит пользователя за спам на указанное время."""
        self._ensure_db_loaded()
        if minutes is None:
            minutes = settings.spam_ban_minutes
        with self._lock:
            self._maybe_cleanup()
            expires = datetime.now() + timedelta(minutes=minutes)
            self._spam_bans[user_id] = expires
            self._save_spam_ban(user_id, expires)
            logger.info(
                "Пользователь %d принудительно забанен за спам на %d мин",
                user_id,
                minutes,
            )

    def record_adult_violation(self, user_id: int) -> bool:
        """
        Фиксирует нарушение 18+ для пользователя.
        Возвращает True, если пользователь получил бан (превышен лимит).
        """
        self._ensure_db_loaded()
        now = datetime.now()

        with self._lock:
            self._maybe_cleanup()

            times = self._adult_violations[user_id]

            while times and times[0] < now - timedelta(minutes=settings.adult_violation_window_minutes):
                times.popleft()

            times.append(now)
            self._save_adult_violation(user_id, now)
            self._cleanup_old_violations(user_id, now - timedelta(minutes=settings.adult_violation_window_minutes))

            if len(times) >= settings.adult_violation_limit:
                expires = now + timedelta(minutes=settings.adult_ban_minutes)
                self._adult_bans[user_id] = expires
                self._save_adult_ban(user_id, expires, len(times))
                logger.warning(
                    "Пользователь %d забанен на %d мин за 18+ контент (нарушений: %d)",
                    user_id,
                    settings.adult_ban_minutes,
                    len(times),
                )
                return True

            logger.info(
                "18+ нарушение #%d для пользователя %d (бан при %d)",
                len(times),
                user_id,
                settings.adult_violation_limit,
            )
            return False

    def is_adult_banned(self, user_id: int) -> bool:
        """Проверяет, находится ли пользователь в бане за 18+ контент."""
        self._ensure_db_loaded()
        with self._lock:
            ban_exp = self._adult_bans.get(user_id)
            if ban_exp is None:
                return False
            if ban_exp > datetime.now():
                return True
            del self._adult_bans[user_id]
            if user_id in self._adult_violations:
                self._adult_violations[user_id].clear()
            self._remove_adult_ban(user_id)
            logger.info("Бан 18+ для пользователя %d истёк — очищен счётчик", user_id)
            return False

    def reset(self) -> None:
        """Полный сброс состояния трекера (для тестов)."""
        with self._lock:
            self._ratelimit_data.clear()
            self._spam_bans.clear()
            self._adult_bans.clear()
            self._adult_violations.clear()
            self._db_loaded = False
            self._last_cleanup = datetime.now()

        # Очищаем БД
        def _clear():
            with get_connection() as conn:
                conn.execute("DELETE FROM spam_bans")
                conn.execute("DELETE FROM adult_bans")
                conn.execute("DELETE FROM adult_violations")
                conn.commit()

        try:
            retry_on_lock(_clear)
            logger.debug("Состояние SpamTracker сброшено (в памяти и в БД)")
        except Exception as e:
            logger.exception("Ошибка сброса SpamTracker в БД: %s", e)


_tracker = SpamTracker()


def check_ratelimit(user_id: int, max_msgs: int = 20, window_minutes: int = 5) -> bool:
    return _tracker.check_ratelimit(user_id, max_msgs, window_minutes)


def is_spam_banned(user_id: int) -> bool:
    return _tracker.is_spam_banned(user_id)


def ban_for_spam(user_id: int, minutes: int | None = None) -> None:
    if minutes is None:
        minutes = settings.spam_ban_minutes
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
