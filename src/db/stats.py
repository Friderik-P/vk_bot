# vk_bot/src/db/stats.py
"""Счётчики статистики бота (таблица stats, id=1)."""

import logging

from .connection import get_connection, retry_on_lock

logger = logging.getLogger(__name__)


def increment_stats(total: int = 0, llm: int = 0, errors: int = 0) -> None:
    """Атомарно увеличивает счётчики в stats (id=1)."""
    if total == 0 and llm == 0 and errors == 0:
        return

    def _inc():
        with get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE stats
                SET
                    total_messages = total_messages + ?,
                    llm_messages = llm_messages + ?,
                    errors = errors + ?
                WHERE id = 1
                """,
                (total, llm, errors),
            )
            conn.commit()

            if cur.rowcount == 0:
                # Строки id=1 нет — создаём
                logger.warning("stats: строка id=1 не найдена, пересоздаю")
                conn.execute(
                    "INSERT OR IGNORE INTO stats (id, total_messages, llm_messages, errors) "
                    "VALUES (1, ?, ?, ?)",
                    (total, llm, errors),
                )
                conn.commit()

            logger.debug(
                "Статистика обновлена: total=%d, llm=%d, errors=%d",
                total, llm, errors,
            )

    try:
        retry_on_lock(_inc)
    except Exception as e:
        logger.exception("Ошибка обновления статистики: %s", e)


def get_stats() -> dict:
    """Возвращает текущую статистику как dict с фиксированными ключами."""

    def _get():
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT total_messages, llm_messages, errors FROM stats WHERE id = 1"
            )
            row = cur.fetchone()
            if row:
                return {
                    "total_messages": row["total_messages"],
                    "llm_messages": row["llm_messages"],
                    "errors": row["errors"],
                }
            return {"total_messages": 0, "llm_messages": 0, "errors": 0}

    try:
        return retry_on_lock(_get)
    except Exception as e:
        logger.exception("Ошибка чтения статистики: %s", e)
        return {"total_messages": 0, "llm_messages": 0, "errors": 0}
