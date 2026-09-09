# vk_bot/src/db/users.py
"""CRUD для пользователей и игнор-листа (заблокировавших бот)."""

import logging

from .connection import get_connection, retry_on_lock

logger = logging.getLogger(__name__)


def load_peer_ids() -> set[int]:
    """Возвращает set всех user_id из БД."""

    def _load():
        with get_connection() as conn:
            cur = conn.execute("SELECT user_id FROM users")
            ids = {row["user_id"] for row in cur.fetchall()}
            logger.debug("Загружено %d пользователей из SQLite.", len(ids))
            return ids

    try:
        return retry_on_lock(_load)
    except Exception as e:
        logger.exception("Ошибка чтения из БД: %s", e)
        return set()


def add_peer_id(peer_ids_set: set[int], user_id: int) -> set[int]:
    """
    Добавляет user_id, если его ещё нет. Возвращает обновлённый set.
    Сначала пишет в БД, потом мутирует set — чтобы при ошибке БД
    set не рассинхронизировался с сохранёнными данными.
    """
    if not isinstance(user_id, int) or user_id <= 0:
        return peer_ids_set

    # Если уже в set — обновляем last_seen в БД и выходим
    if user_id in peer_ids_set:
        def _touch():
            with get_connection() as conn:
                conn.execute(
                    "UPDATE users SET last_seen = datetime('now') WHERE user_id = ?",
                    (user_id,)
                )
                conn.commit()

        try:
            retry_on_lock(_touch)
        except Exception as e:
            logger.debug("Не удалось обновить last_seen для user_id=%d: %s", user_id, e)
        return peer_ids_set

    def _add():
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
                (user_id,)
            )
            conn.execute(
                "UPDATE users SET last_seen = datetime('now') WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()

    try:
        retry_on_lock(_add)
        # БД успешно обновлена — теперь безопасно мутировать set
        peer_ids_set.add(user_id)
        logger.debug("Добавлен новый пользователь user_id=%d", user_id)
    except Exception as e:
        logger.error("Ошибка при добавлении пользователя user_id=%d: %s", user_id, e)

    return peer_ids_set


def mark_user_blocked(user_id: int, reason: str = "") -> None:
    """Помечает пользователя как заблокировавшего бота (для рассылки)."""

    def _mark():
        with get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO blocked_users (user_id, blocked_at, reason)
                VALUES (?, datetime('now'), ?)
                """,
                (user_id, reason)
            )
            conn.commit()
            logger.info(
                "Пользователь user_id=%d добавлен в игнор-лист (причина: %s)",
                user_id, reason
            )

    try:
        retry_on_lock(_mark)
    except Exception as e:
        logger.exception("Ошибка при добавлении в игнор-лист: %s", e)


def get_blocked_ids() -> set[int]:
    """Возвращает set ID пользователей из игнор-листа."""

    def _get():
        with get_connection() as conn:
            cur = conn.execute("SELECT user_id FROM blocked_users")
            return {row["user_id"] for row in cur.fetchall()}

    try:
        return retry_on_lock(_get)
    except Exception as e:
        logger.exception("Ошибка чтения игнор-листа: %s", e)
        return set()


__all__ = ["load_peer_ids", "add_peer_id", "mark_user_blocked", "get_blocked_ids"]
