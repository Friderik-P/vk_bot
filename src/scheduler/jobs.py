# vk_bot/src/scheduler/jobs.py
"""Задачи планировщика: рассылка, health-check, очистка истории."""

import logging

from .constants import BROADCAST_MESSAGE, DEFAULT_DELAY_SECONDS, PRUNE_KEEP_RECORDS

logger = logging.getLogger(__name__)


def job_broadcast(vk_api_instance, peer_ids_func, delay_seconds: float = DEFAULT_DELAY_SECONDS):
    """Рассылает сообщение всем активным пользователям."""
    try:
        peer_ids = peer_ids_func()
        if not peer_ids:
            logger.info("[Scheduler] Нет пользователей для рассылки.")
            return

        from ..services import broadcast_hello

        broadcast_hello(
            vk_api_instance=vk_api_instance,
            user_ids=peer_ids,
            delay_seconds=delay_seconds,
            message=BROADCAST_MESSAGE,
        )
    except Exception:
        logger.exception("[Scheduler] Ошибка в job_broadcast")


def job_health(vk_api_instance, chat_client, admin_ids):
    """Проверяет доступность GigaChat и уведомляет администраторов."""
    try:
        if chat_client is None:
            logger.debug("[Health] chat_client не передан — пропускаю проверку.")
            return

        from ..services import run_health_check

        run_health_check(
            chat_client=chat_client,
            vk_api=vk_api_instance,
            admin_ids=admin_ids or [],
        )
    except Exception:
        logger.exception("[Scheduler] Ошибка в job_health")


def job_prune():
    """Очищает старую историю диалогов у всех пользователей (раз в неделю)."""
    try:
        from ..db import prune_all_history

        prune_all_history(keep=PRUNE_KEEP_RECORDS)
        logger.info(
            "[Scheduler] Очистка истории выполнена (оставлено по %d записей).",
            PRUNE_KEEP_RECORDS,
        )
    except Exception:
        logger.exception("[Scheduler] Ошибка в job_prune")


__all__ = ["job_broadcast", "job_health", "job_prune"]
