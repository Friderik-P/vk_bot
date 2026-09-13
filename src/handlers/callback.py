# vk_bot/src/handlers/callback.py
"""Обработка callback-событий (нажатий на inline-кнопки)."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..server import Bot

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

    logger.info(
        "Callback received: peer_id=%s, callback_data=%s",
        peer_id, callback_data,
    )

    # Сюда позже добавишь логику по callback_data
    # Пример:
    # if callback_data == "btn_help":
    #     server.send_message(peer_id, "Это раздел помощи!")
    #     return True

    return True


__all__ = ["handle_callback"]
