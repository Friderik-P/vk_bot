# vk_bot/src/services/broadcaster.py
"""Рассылка сообщений по списку пользователей VK."""

import time
import logging
from vk_api.utils import get_random_id

from ..constants import VK_ERROR_RATE_LIMIT, VK_ERROR_USER_BLOCKED, VK_ERROR_MSG_TOO_LONG, VK_ERROR_CHAT_NOT_FOUND
from ..db import get_blocked_ids, mark_user_blocked

logger = logging.getLogger(__name__)


def broadcast_hello(
    vk_api_instance,
    user_ids,
    delay_seconds=0.2,
    message="Приветики!!! Я снова ожил! Мяу!",
    max_retries=2,
):
    """
    Рассылка сообщений по списку пользователей.

    :param vk_api_instance: экземпляр vk_api (self.vk_api)
    :param user_ids: iterable из ID пользователей (from_id)
    :param delay_seconds: пауза между сообщениями
    :param message: текст сообщения
    :param max_retries: макс. число повторных попыток для одного пользователя
    :return: (count_sent, count_failed)
    """
    filtered_ids = [
        uid for uid in user_ids
        if isinstance(uid, int) and uid > 0
    ]

    blocked_ids = get_blocked_ids()
    if blocked_ids:
        before = len(filtered_ids)
        filtered_ids = [uid for uid in filtered_ids if uid not in blocked_ids]
        skipped = before - len(filtered_ids)
        if skipped:
            logger.info("Пропущено %d пользователей из игнор-листа.", skipped)

    if not filtered_ids:
        logger.warning(
            "Список пользователей пуст или все в игнор-листе. Рассылка пропущена."
        )
        return 0, 0

    count_sent = 0
    count_failed = 0
    logger.info(
        "Начинаем рассылку по %d пользователям (пауза %.2f сек между сообщениями)",
        len(filtered_ids),
        delay_seconds,
    )

    for user_id in filtered_ids:
        sent = False
        for attempt in range(1, max_retries + 2):
            try:
                vk_api_instance.messages.send(
                    peer_id=user_id,
                    message=message,
                    random_id=get_random_id(),
                )
                count_sent += 1
                sent = True
                break

            except Exception as e:
                vk_error_code = getattr(e, "code", None)

                # Временная ошибка: лимит запросов — пробуем ещё
                if vk_error_code == VK_ERROR_RATE_LIMIT:
                    wait_time = 5 * attempt
                    logger.warning(
                        "Лимит запросов VK API (код %d) на user_id=%d. "
                        "Попытка %d/%d, ждём %d сек.",
                        vk_error_code,
                        user_id,
                        attempt,
                        max_retries + 1,
                        wait_time,
                    )
                    time.sleep(wait_time)
                    continue

                # Окончательные ошибки: пользователь недоступен
                elif vk_error_code in (VK_ERROR_USER_BLOCKED, VK_ERROR_MSG_TOO_LONG, VK_ERROR_CHAT_NOT_FOUND):
                    logger.debug(
                        "Пользователь user_id=%d недоступен (код %d). "
                        "Добавляем в игнор-лист.",
                        user_id,
                        vk_error_code,
                    )
                    mark_user_blocked(user_id, reason=f"vk_code_{vk_error_code}")
                    count_failed += 1
                    sent = True
                    break

                else:
                    logger.error(
                        "Не удалось отправить сообщение user_id=%d (код %s): %s",
                        user_id,
                        vk_error_code,
                        e,
                    )
                    count_failed += 1
                    sent = True
                    break

        if not sent:
            count_failed += 1
            logger.warning("Все попытки отправки для user_id=%d исчерпаны.", user_id)

        time.sleep(delay_seconds)

    logger.info("Рассылка завершена: отправлено=%d, ошибок=%d", count_sent, count_failed)
    return count_sent, count_failed


__all__ = ["broadcast_hello"]
