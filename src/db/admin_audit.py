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


__all__ = ["log_admin_action"]
