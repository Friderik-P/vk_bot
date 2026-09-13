# vk_bot/src/db/chat_history.py
"""CRUD для истории диалогов и массовая очистка старых записей."""

import logging

from .connection import get_connection, retry_on_lock
from ..config import settings

logger = logging.getLogger(__name__)

# Допустимые роли для GigaChat API
_VALID_ROLES = frozenset({"user", "assistant"})


def save_message(user_id: int, role: str, content: str) -> None:
    """
    Сохраняет одно сообщение в историю диалога.
    Подрезка старых записей выполняется только при превышении лимита,
    а не при каждом сообщении.
    """

    def _save():
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM chat_history WHERE user_id = ?",
                (user_id,)
            )
            count = cur.fetchone()[0]

            conn.execute(
                "INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content)
            )

            if count + 1 > settings.max_history_per_user:
                conn.execute(
                    """
                    DELETE FROM chat_history
                    WHERE user_id = ?
                      AND id NOT IN (
                          SELECT id FROM chat_history
                          WHERE user_id = ?
                          ORDER BY id DESC
                          LIMIT ?
                      )
                    """,
                    (user_id, user_id, settings.max_history_per_user)
                )

            conn.commit()

    try:
        retry_on_lock(_save)
    except Exception as e:
        logger.exception("Ошибка сохранения сообщения в БД: %s", e)


def load_history(user_id: int, limit: int = 20) -> list[dict]:
    """
    Возвращает последние `limit` сообщений пользователя
    в виде списка словарей [{"role": ..., "content": ...}, ...].
    """
    if limit < 0:
        limit = 0

    def _load():
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT role, content FROM chat_history "
                "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            )
            rows = cur.fetchall()
            return [{"role": row["role"], "content": row["content"]}
                    for row in reversed(rows)]

    try:
        return retry_on_lock(_load)
    except Exception as e:
        logger.exception("Ошибка загрузки истории из БД: %s", e)
        return []


def clear_chat_history(user_id: int) -> None:
    """Удаляет всю историю диалога пользователя."""

    def _clear():
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM chat_history WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()

    try:
        retry_on_lock(_clear)
    except Exception as e:
        logger.exception("Ошибка очистки истории в БД: %s", e)


def prune_all_history(keep: int = 500) -> None:
    """
    Массовая очистка старой истории для всех пользователей.
    Оставляет последние `keep` записей у каждого.
    Вызывается планировщиком раз в неделю.
    """
    if keep < 1:
        logger.warning("prune_all_history: keep=%d < 1, пропускаю (нечего оставлять).", keep)
        return

    def _prune():
        with get_connection() as conn:
            conn.execute(
                """
                DELETE FROM chat_history
                WHERE id NOT IN (
                    SELECT id FROM (
                        SELECT id,
                               ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY id DESC) AS rn
                        FROM chat_history
                    ) WHERE rn <= ?
                )
                """,
                (keep,)
            )
            conn.commit()
            logger.info("Массовая очистка истории выполнена (оставлено по %d записей).", keep)

    try:
        retry_on_lock(_prune)
    except Exception as e:
        logger.exception("Ошибка массовой очистки истории: %s", e)


__all__ = ["save_message", "load_history", "clear_chat_history", "prune_all_history"]
