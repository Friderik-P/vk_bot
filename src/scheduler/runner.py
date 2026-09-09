# vk_bot/src/scheduler/runner.py
"""Запуск и управление фоновым планировщиком."""

import threading
import schedule
import time
import logging

from .jobs import job_broadcast, job_health, job_prune, get_next_health_interval, reset_health_interval
from .constants import (
    DEFAULT_DELAY_SECONDS,
    DEFAULT_HEALTH_INTERVAL_MINUTES,
    PRUNE_TIME,
)

logger = logging.getLogger(__name__)

_scheduler_running = False
_health_job = None
_current_health_interval = DEFAULT_HEALTH_INTERVAL_MINUTES


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
    :param health_interval_minutes: начальный интервал health-check (минут)
    """
    global _scheduler_running, _health_job, _current_health_interval

    if _scheduler_running:
        logger.warning("Планировщик уже запущен, повторный запуск пропущен.")
        return

    _scheduler_running = True
    _current_health_interval = health_interval_minutes
    schedule.clear()

    schedule.every(24).hours.do(
        job_broadcast,
        vk_api_instance=vk_api_instance,
        peer_ids_func=peer_ids_func,
        delay_seconds=delay_seconds,
    )

    _health_job = schedule.every(health_interval_minutes).minutes.do(
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
        global _current_health_interval, _health_job
        while True:
            try:
                schedule.run_pending()

                # Динамический backoff для health-check
                if _health_job is not None:
                    next_interval = get_next_health_interval()
                    if next_interval is not None and next_interval != _current_health_interval:
                        logger.info(
                            "[Scheduler] Перепланирую health-check: %d -> %d мин",
                            _current_health_interval,
                            next_interval,
                        )
                        schedule.cancel_job(_health_job)
                        _health_job = schedule.every(next_interval).minutes.do(
                            job_health,
                            vk_api_instance=vk_api_instance,
                            chat_client=chat_client,
                            admin_ids=admin_ids,
                        )
                        _current_health_interval = next_interval
            except Exception:
                logger.exception(
                    "[Scheduler] Неперехваченное исключение в цикле планировщика"
                )
            time.sleep(1)

    thread = threading.Thread(target=_run, daemon=True, name="scheduler-loop")
    thread.start()


def set_health_interval(minutes: int) -> None:
    """Принудительно устанавливает интервал health-check."""
    global _current_health_interval
    _current_health_interval = max(1, minutes)


__all__ = ["start_scheduler", "set_health_interval"]
