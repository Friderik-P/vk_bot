# vk_bot/src/scheduler/runner.py
"""Запуск и управление фоновым планировщиком."""

import threading
import schedule
import time
import logging

from .jobs import job_broadcast, job_health, job_prune
from .constants import (
    DEFAULT_DELAY_SECONDS,
    DEFAULT_HEALTH_INTERVAL_MINUTES,
    PRUNE_TIME,
)

logger = logging.getLogger(__name__)

_scheduler_running = False


def start_scheduler(
    vk_api_instance,
    peer_ids_func,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    chat_client=None,
    admin_ids=None,
    health_interval_minutes: int = DEFAULT_HEALTH_INTERVAL_MINUTES,
):
    """
    Запускает фоновую рассылку и обслуживание по расписанию.

    :param vk_api_instance: self.vk_api из Server
    :param peer_ids_func: функция, возвращающая актуальный set ID пользователей
    :param delay_seconds: пауза между отдельными сообщениями в рассылке
    :param chat_client: экземпляр клиента GigaChat (для health-check)
    :param admin_ids: список ID администраторов
    :param health_interval_minutes: как часто проверять GigaChat (минут)
    """
    global _scheduler_running

    if _scheduler_running:
        logger.warning("Планировщик уже запущен, повторный запуск пропущен.")
        return

    _scheduler_running = True
    schedule.clear()

    schedule.every(24).hours.do(
        job_broadcast,
        vk_api_instance=vk_api_instance,
        peer_ids_func=peer_ids_func,
        delay_seconds=delay_seconds,
    )

    schedule.every(health_interval_minutes).minutes.do(
        job_health,
        vk_api_instance=vk_api_instance,
        chat_client=chat_client,
        admin_ids=admin_ids,
    )

    schedule.every().monday.at(PRUNE_TIME).do(job_prune)

    def _run():
        logger.info(
            "[Scheduler] Планировщик запущен. Рассылка, health-check и очистка активны."
        )
        while True:
            try:
                schedule.run_pending()
            except Exception:
                logger.exception(
                    "[Scheduler] Неперехваченное исключение в цикле планировщика"
                )
            time.sleep(1)

    thread = threading.Thread(target=_run, daemon=True, name="scheduler-loop")
    thread.start()


__all__ = ["start_scheduler"]
