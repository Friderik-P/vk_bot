# vk_bot/src/handlers/callback.py
"""Обработка callback-событий (нажатий на inline-кнопки)."""

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..server import Bot

from ..admins import get_admins

logger = logging.getLogger(__name__)


def handle_callback(server: "Bot", event: Any) -> bool:
    """
    Обрабатывает callback-события (нажатия на inline-кнопки).
    Для MESSAGE_EVENT структура: event.object содержит
    user_id, peer_id, payload, conversation_message_id.
    """
    obj = getattr(event, "object", None)
    if obj is None:
        logger.warning("Callback: event.object is None")
        return False

    peer_id = getattr(obj, "peer_id", None)
    if not peer_id:
        logger.warning("Не удалось определить peer_id для callback-события")
        return False

    raw_payload = getattr(obj, "payload", None)
    callback_data = None
    if isinstance(raw_payload, str):
        callback_data = raw_payload
    elif isinstance(raw_payload, dict):
        callback_data = raw_payload.get("callback_data") or raw_payload.get("command")

    if not callback_data:
        logger.info("Callback received: peer_id=%s, пустой payload", peer_id)
        return True

    user_id = getattr(obj, "user_id", None)
    if not user_id or user_id <= 0:
        logger.warning("Не удалось определить user_id для callback-события")
        return False

    logger.info(
        "Callback received: peer_id=%s, user_id=%s, callback_data=%s",
        peer_id, user_id, callback_data,
    )

    # Обрабатываем админ-команды из инлайн-клавиатуры
    admin_handler = getattr(server, "admin_handler", None)
    if admin_handler and user_id in get_admins():
        handled = admin_handler.handle(user_id, peer_id, callback_data)
        if handled:
            return True

    return True


__all__ = ["handle_callback"]
