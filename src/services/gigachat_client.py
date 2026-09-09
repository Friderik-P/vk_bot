# vk_bot/src/services/gigachat_client.py
"""
Клиент GigaChat для VK-бота.

Предоставляет функцию get_client(), которая возвращает экземпляр клиента
либо None, если не задан GIGACHAT_AUTH_KEY.

max_retries=0 — для health-check (быстрые провалы).
max_retries=1 — для чата (используется в chat.py).
"""

import logging

from ..config import GIGACHAT_AUTH_KEY, GIGACHAT_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

try:
    from gigachat import GigaChat
except ImportError:
    logger.error("Не удалось импортировать gigachat. Установите: pip install gigachat")
    raise


def get_client(max_retries: int = 1) -> GigaChat | None:
    """
    Возвращает клиент GigaChat или None, если ключ не задан.

    :param max_retries: число повторных попыток (0 — health-check, 1 — чат)
    """
    if not GIGACHAT_AUTH_KEY:
        logger.warning("GIGACHAT_AUTH_KEY не задан — GigaChat отключён.")
        return None

    try:
        client = GigaChat(
            credentials=GIGACHAT_AUTH_KEY,
            scope="GIGACHAT_API_PERS",
            verify_ssl_certs=False,
            timeout=GIGACHAT_TIMEOUT_SECONDS,
            max_retries=max_retries,
        )
        logger.info(
            "Клиент GigaChat инициализирован "
            "(timeout=%d сек, retries=%d).",
            GIGACHAT_TIMEOUT_SECONDS,
            max_retries,
        )
        return client
    except Exception as e:
        logger.error("Ошибка инициализации клиента GigaChat: %s", e)
        return None
