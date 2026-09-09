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
import unicodedata

from ..config import ADULT_VIOLATION_LIMIT, ADULT_VIOLATION_WINDOW_MINUTES, ADULT_BAN_MINUTES, SPAM_BAN_MINUTES

logger = logging.getLogger(__name__)

# Глобальный лок для всех in-memory структур
_lock = threading.Lock()

# В памяти: лимит сообщений (скользящее окно)
# maxlen не нужен — скользящее окно очищается через popleft()
_ratelimit_data: dict[int, deque] = defaultdict(deque)
# В памяти: баны за спам (user_id -> datetime окончания бана)
_spam_bans: dict[int, datetime] = {}
# В памяти: баны за 18+ контент (user_id -> datetime окончания бана)
_adult_bans: dict[int, datetime] = {}
# В памяти: нарушения 18+ (user_id -> deque времен)
_adult_violations: dict[int, deque] = defaultdict(deque)

# Интервал периодической очистки (секунды)
_CLEANUP_INTERVAL = 300  # 5 минут
_last_cleanup = datetime.now()


def _maybe_cleanup() -> None:
    """Периодически очищает истёкшие баны и пустые deque'ы. Вызывать под локом."""
    global _last_cleanup
    now = datetime.now()
    if (now - _last_cleanup).total_seconds() < _CLEANUP_INTERVAL:
        return
    _last_cleanup = now

    # Очистка истёкших банов
    expired_spam = [uid for uid, exp in _spam_bans.items() if exp <= now]
    for uid in expired_spam:
        del _spam_bans[uid]

    expired_adult = [uid for uid, exp in _adult_bans.items() if exp <= now]
    for uid in expired_adult:
        del _adult_bans[uid]
        if uid in _adult_violations:
            _adult_violations[uid].clear()

    # Очистка пустых deque'ов
    empty_rl = [uid for uid, dq in _ratelimit_data.items() if not dq]
    for uid in empty_rl:
        del _ratelimit_data[uid]

    empty_av = [uid for uid, dq in _adult_violations.items() if not dq]
    for uid in empty_av:
        del _adult_violations[uid]

    if expired_spam or expired_adult or empty_rl or empty_av:
        logger.debug(
            "Очистка spam-данных: удалено банов спам=%d, 18+=%d, "
            "пустых записей ratelimit=%d, adult=%d",
            len(expired_spam), len(expired_adult),
            len(empty_rl), len(empty_av),
        )


def check_ratelimit(user_id: int, max_msgs: int = 20, window_minutes: int = 5) -> bool:
    """
    Проверяет лимит сообщений в скользящем окне.
    Если лимит превышен — ставит бан на SPAM_BAN_MINUTES минут и возвращает False.
    """
    now = datetime.now()

    with _lock:
        _maybe_cleanup()

        times = _ratelimit_data[user_id]

        while times and times[0] < now - timedelta(minutes=window_minutes):
            times.popleft()

        if len(times) >= max_msgs:
            _spam_bans[user_id] = now + timedelta(minutes=SPAM_BAN_MINUTES)
            logger.warning(
                "Пользователь %d превысил лимит сообщений — бан на %d мин",
                user_id, SPAM_BAN_MINUTES,
            )
            return False

        times.append(now)
        return True


def is_spam_banned(user_id: int) -> bool:
    """Проверяет, находится ли пользователь в бане за спам."""
    with _lock:
        ban_exp = _spam_bans.get(user_id)
        if ban_exp is None:
            return False
        if ban_exp > datetime.now():
            return True
        # Бан истёк — очищаем бан и историю сообщений,
        # чтобы пользователь начинал с чистого листа
        del _spam_bans[user_id]
        if user_id in _ratelimit_data:
            _ratelimit_data[user_id].clear()
        return False


def ban_for_spam(user_id: int, minutes: int = SPAM_BAN_MINUTES) -> None:
    """Принудительно банит пользователя за спам на указанное время."""
    with _lock:
        _maybe_cleanup()
        _spam_bans[user_id] = datetime.now() + timedelta(minutes=minutes)
        logger.info(
            "Пользователь %d принудительно забанен за спам на %d мин",
            user_id, minutes,
        )


# 18+ нарушения: счётчик + бан


def record_adult_violation(user_id: int) -> bool:
    """
    Фиксирует нарушение 18+ для пользователя.
    Возвращает True, если пользователь получил бан (превышен лимит).
    """
    now = datetime.now()

    with _lock:
        _maybe_cleanup()

        times = _adult_violations[user_id]

        while times and times[0] < now - timedelta(minutes=ADULT_VIOLATION_WINDOW_MINUTES):
            times.popleft()

        times.append(now)

        if len(times) >= ADULT_VIOLATION_LIMIT:
            _adult_bans[user_id] = now + timedelta(minutes=ADULT_BAN_MINUTES)
            logger.warning(
                "Пользователь %d забанен на %d мин за 18+ контент (нарушений: %d)",
                user_id, ADULT_BAN_MINUTES, len(times),
            )
            return True

        logger.info(
            "18+ нарушение #%d для пользователя %d (бан при %d)",
            len(times), user_id, ADULT_VIOLATION_LIMIT,
        )
        return False


def is_adult_banned(user_id: int) -> bool:
    """Проверяет, находится ли пользователь в бане за 18+ контент."""
    with _lock:
        ban_exp = _adult_bans.get(user_id)
        if ban_exp is None:
            return False
        if ban_exp > datetime.now():
            return True
        del _adult_bans[user_id]
        if user_id in _adult_violations:
            _adult_violations[user_id].clear()
        logger.info("Бан 18+ для пользователя %d истёк — очищен счётчик", user_id)
        return False
