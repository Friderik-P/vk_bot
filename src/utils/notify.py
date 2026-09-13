# vk_bot/src/utils/notify.py
"""Утилиты для уведомления администраторов."""

import logging
from typing import Callable, List, Optional

from vk_api.utils import get_random_id
from vk_api.exceptions import ApiError

from ..constants import VK_ERROR_USER_BLOCKED

logger = logging.getLogger(__name__)


def notify_admins(
    vk_api,
    admin_ids: List[int],
    message: str,
    send_func: Optional[Callable[[int, str], None]] = None,
) -> None:
    """
    Отправляет сообщение всем администраторам.

    :param vk_api: Экземпляр VK API (используется если send_func не указан).
    :param admin_ids: Список ID администраторов.
    :param message: Текст сообщения.
    :param send_func: Опциональная функция для отправки (peer_id, message) -> None.
    """
    if not admin_ids:
        logger.warning("Список admin_ids пуст — уведомления не будут отправлены.")
        return

    for admin_id in admin_ids:
        try:
            if send_func is not None and callable(send_func):
                send_func(admin_id, message)
            else:
                vk_api.messages.send(
                    peer_id=admin_id,
                    message=message,
                    random_id=get_random_id(),
                )
        except ApiError as e:
            if e.code == VK_ERROR_USER_BLOCKED:
                logger.info(
                    "Админ %d не принимает сообщения от группы — пропускаем.",
                    admin_id,
                )
            else:
                logger.error(
                    "VK API ошибка при уведомлении админа %d: [%s] %s",
                    admin_id, e.code, e,
                )
        except Exception as e:
            logger.exception(
                "Не удалось уведомить админа %d: %s", admin_id, e
            )


__all__ = ["notify_admins"]
