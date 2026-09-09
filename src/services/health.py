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

logger = logging.getLogger(__name__)

PING_TIMEOUT_SECONDS = 10

_lock = threading.Lock()
_last_status: str = "unknown"
_last_error_msg: Optional[str] = None


def _ping_gigachat(chat_client) -> Tuple[bool, Optional[str]]:
    """
    Отправляет минимальный запрос к GigaChat.
    Таймаут обеспечивается клиентом (httpx), ручной поток не нужен.

    :return: (True, None) при успехе, (False, error_msg) при ошибке.
    """
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "ping"}],
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
) -> None:
    """
    Запускает автоматическую проверку GigaChat по расписанию.
    Уведомляет админов только при смене состояния.
    """
    global _last_status, _last_error_msg

    now_time = datetime.now()
    time_str = now_time.strftime("%H:%M:%S")

    is_ok, error_msg = _ping_gigachat(chat_client)

    with _lock:
        if is_ok:
            if _last_status == "down":
                logger.info("[Health] GigaChat снова доступен! Восстановлено в %s", time_str)
                _notify_admins(
                    vk_api,
                    admin_ids,
                    send_func,
                    f"✅ GigaChat снова доступен!\nВосстановлено в {time_str}",
                )
            _last_status = "ok"
            _last_error_msg = None
            logger.debug("[Health] GigaChat доступен.")
        else:
            if _last_status != "down":
                logger.error("[Health] GigaChat недоступен: %s", error_msg or "Неизвестная ошибка")
                _notify_admins(
                    vk_api,
                    admin_ids,
                    send_func,
                    (
                        f"⚠️ GigaChat недоступен с {time_str}\n"
                        f"Ошибка: {error_msg or 'Неизвестная ошибка'}"
                    ),
                )
            else:
                logger.debug(
                    "[Health] GigaChat всё ещё недоступен: %s",
                    error_msg or "Нет сообщения об ошибке",
                )
            _last_status = "down"
            _last_error_msg = error_msg


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


def _notify_admins(
    vk_api,
    admin_ids: List[int],
    send_func: Optional[Callable[[int, str], None]],
    message: str,
) -> None:
    """Отправляет сообщение всем администраторам."""
    from vk_api.utils import get_random_id
    from vk_api.exceptions import ApiError

    if not admin_ids:
        logger.warning("[Health] Список admin_ids пуст — уведомления не будут отправлены.")
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
            if e.code == 901:
                logger.info(
                    "[Health] Админ %d не принимает сообщения от группы — пропускаем.",
                    admin_id,
                )
            else:
                logger.error(
                    "[Health] VK API ошибка при уведомлении админа %d: [%s] %s",
                    admin_id, e.code, e,
                )
        except Exception as e:
            logger.exception(
                "[Health] Не удалось уведомить админа %d: %s", admin_id, e
            )
