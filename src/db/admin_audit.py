# vk_bot/src/db/admin_audit.py
"""Audit log для админ-команд."""

import logging

from .connection import get_connection, retry_on_lock

logger = logging.getLogger(__name__)


def log_admin_action(admin_id: int, command: str, peer_id: int) -> None:
    """Записывает действие администратора в audit log."""

    def _log():
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO admin_audit (admin_id, command, peer_id) VALUES (?, ?, ?)",
                (admin_id, command, peer_id),
            )
            conn.commit()

    try:
        retry_on_lock(_log)
    except Exception as e:
        logger.exception("Ошибка записи в audit log: %s", e)


def get_admin_audit(admin_id: int | None = None, limit: int = 50) -> list[dict]:
    """Возвращает последние записи audit log."""

    def _get():
        with get_connection() as conn:
            if admin_id is not None:
                cur = conn.execute(
                    "SELECT admin_id, command, peer_id, created_at FROM admin_audit "
                    "WHERE admin_id = ? ORDER BY id DESC LIMIT ?",
                    (admin_id, limit),
                )
            else:
                cur = conn.execute(
                    "SELECT admin_id, command, peer_id, created_at FROM admin_audit "
                    "ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            return [
                {
                    "admin_id": row["admin_id"],
                    "command": row["command"],
                    "peer_id": row["peer_id"],
                    "created_at": row["created_at"],
                }
                for row in cur.fetchall()
            ]

    try:
        return retry_on_lock(_get)
    except Exception as e:
        logger.exception("Ошибка чтения audit log: %s", e)
        return []


__all__ = ["log_admin_action", "get_admin_audit"]
