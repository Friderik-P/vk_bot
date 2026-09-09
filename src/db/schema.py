# vk_bot/src/db/schema.py
"""Инициализация схемы БД: создание таблиц и индексов."""

import logging

from .connection import get_connection, retry_on_lock

logger = logging.getLogger(__name__)


def init_db() -> None:
    """
    Создаёт таблицы и индексы, если их нет.
    Бросает исключение при провале — main.py должен остановить запуск.
    """

    def _init() -> None:
        with get_connection() as conn:
            # Гарантируем WAL на самом раннем этапе
            conn.execute("PRAGMA journal_mode=WAL")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_seen DATETIME NOT NULL DEFAULT (datetime('now')),
                    last_seen DATETIME NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blocked_users (
                    user_id INTEGER PRIMARY KEY,
                    blocked_at DATETIME DEFAULT (datetime('now')),
                    reason TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT (datetime('now'))
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_history_user "
                "ON chat_history (user_id, id)"
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    total_messages INTEGER NOT NULL DEFAULT 0,
                    llm_messages INTEGER NOT NULL DEFAULT 0,
                    errors INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO stats (id, total_messages, llm_messages, errors) "
                "VALUES (1, 0, 0, 0)"
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS admin_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    command TEXT NOT NULL,
                    peer_id INTEGER NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_admin_audit_admin "
                "ON admin_audit (admin_id, created_at)"
            )
            conn.commit()
            logger.info("База данных инициализирована.")

    # Пробрасываем исключение — main.py должен знать, что БД не готова
    retry_on_lock(_init)


__all__ = ["init_db"]
