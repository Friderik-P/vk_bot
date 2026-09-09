# vk_bot/src/services/health.py
"""
Health-check для GigaChat: автоматическая и ручная проверка доступности,
уведомления администраторов при смене статуса.
"""

import logging
import threading
from datetime import datetime
from typing import Optional, Tuple, Callable, List

import httpx

from ..prompts import MODEL
from ..utils.notify import notify_admins

logger = logging.getLogger(__name__)

PING_TIMEOUT_SECONDS = 10

# Ротирующие короткие промпты для health-check, чтобы избежать
# кэширования/детекции идентичных запросов на стороне GigaChat.
HEALTH_CHECK_PROMPTS: Tuple[str, ...] = (
    "ping",
    "ok",
    "status",
    "ready",
    "alive",
    "test",
    "up",
    "running",
    "online",
    "check",
)

_lock = threading.Lock()
_last_status: str = "unknown"
_last_error_msg: Optional[str] = None
_prompt_index: int = 0
_consecutive_failures: int = 0


def _get_next_prompt() -> str:
    """Возвращает следующий короткий промпт из ротации."""
    global _prompt_index
    prompt = HEALTH_CHECK_PROMPTS[_prompt_index % len(HEALTH_CHECK_PROMPTS)]
    _prompt_index += 1
    return prompt


def _get_backoff_interval_minutes() -> int:
    """
    Вычисляет интервал следующей проверки по линейной градации.
    База 10 минут, шаг +10 минут, максимум 60 минут.
    """
    base = 10
    maximum = 60
    interval = min(base + base * _consecutive_failures, maximum)
    return int(interval)


def _record_success() -> None:
    """Сбрасывает счётчик ошибок после успешной проверки."""
    global _consecutive_failures
    _consecutive_failures = 0


def _record_failure() -> int:
    """Увеличивает счётчик ошибок и возвращает следующий интервал в минутах."""
    global _consecutive_failures
    _consecutive_failures += 1
    return _get_backoff_interval_minutes()


def _ping_gigachat(chat_client) -> Tuple[bool, Optional[str]]:
    """
    Отправляет минимальный запрос к GigaChat.
    Таймаут обеспечивается клиентом (httpx), ручной поток не нужен.

    :return: (True, None) при успехе, (False, error_msg) при ошибке.
    """
    prompt = _get_next_prompt()
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 5,
    }

    try:
        response = chat_client.chat(payload)
    except httpx.ConnectTimeout:
        logger.warning("[Health] Таймаут соединения с GigaChat.")
        return False, "Таймаут соединения"
    except httpx.ConnectError as e:
        logger.warning("[Health] Ошибка соединения с GigaChat: %s", e)
        return False, "Ошибка соединения"
    except httpx.ReadTimeout:
        logger.warning("[Health] Таймаут чтения ответа GigaChat.")
        return False, "Таймаут чтения"
    except httpx.TimeoutException as e:
        logger.warning("[Health] Таймаут при работе с GigaChat: %s", e)
        return False, "Таймаут запроса"
    except Exception as exc:
        error_str = str(exc)
        logger.warning("[Health] Ошибка при запросе к GigaChat: %s", error_str)
        return False, error_str[:200]

    if not response:
        return False, "Пустой ответ от API (None)"

    choices = getattr(response, "choices", None)
    if not choices or len(choices) == 0:
        return False, "Ответ без choices (пустой список)"

    return True, None


def run_health_check(
    chat_client,
    vk_api,
    admin_ids: List[int],
    send_func: Optional[Callable[[int, str], None]] = None,
) -> int:
    """
    Запускает автоматическую проверку GigaChat по расписанию.
    Уведомляет админов только при смене состояния.

    :return: Интервал до следующей проверки в минутах (экспоненциальный backoff).
    """
    global _last_status, _last_error_msg

    now_time = datetime.now()
    time_str = now_time.strftime("%H:%M:%S")

    is_ok, error_msg = _ping_gigachat(chat_client)

    with _lock:
        if is_ok:
            _record_success()
            if _last_status == "down":
                logger.info("[Health] GigaChat снова доступен! Восстановлено в %s", time_str)
                notify_admins(
                    vk_api,
                    admin_ids,
                    f"✅ GigaChat снова доступен!\nВосстановлено в {time_str}",
                    send_func=send_func,
                )
            _last_status = "ok"
            _last_error_msg = None
            logger.debug("[Health] GigaChat доступен.")
        else:
            next_interval = _record_failure()
            if _last_status != "down":
                logger.error("[Health] GigaChat недоступен: %s", error_msg or "Неизвестная ошибка")
                notify_admins(
                    vk_api,
                    admin_ids,
                    (
                        f"⚠️ GigaChat недоступен с {time_str}\n"
                        f"Ошибка: {error_msg or 'Неизвестная ошибка'}"
                    ),
                    send_func=send_func,
                )
            else:
                logger.debug(
                    "[Health] GigaChat всё ещё недоступен: %s",
                    error_msg or "Нет сообщения об ошибке",
                )
            _last_status = "down"
            _last_error_msg = error_msg
            return next_interval

    return _get_backoff_interval_minutes()


def check_gigachat_manual(chat_client) -> str:
    """
    Ручная проверка GigaChat (по команде /health от админа).
    Возвращает строку с отчётом для отправки админу.

    НЕ меняет глобальное состояние _last_status — только для отчёта.
    """
    now_time = datetime.now().strftime("%H:%M:%S")
    is_ok, error_msg = _ping_gigachat(chat_client)

    if is_ok:
        return f"✅ GigaChat доступен (проверка в {now_time})"
    else:
        return (
            f"❌ GigaChat недоступен (проверка в {now_time})\n"
            f"Ошибка: {error_msg or 'Неизвестная ошибка'}"
        )


__all__ = ["run_health_check", "check_gigachat_manual"]
