# vk_bot/src/chat.py
"""
Логика взаимодействия с GigaChat: формирование промптов,
обработка ответов, управление историей диалога и обработка ошибок.

Статистика (total, llm, errors) учитывается в server.py и handlers/message.py.
"""

import logging
import random
import threading

import httpx
from gigachat import GigaChat
from gigachat.exceptions import (
    RateLimitError,
    AuthenticationError,
    GigaChatException,
)

from .config import settings
from .constants import GIGACHAT_API_PERS
from .prompts import (
    MODEL,
    build_system_prompt,
    SILENT_RESPONSES,
    SENSITIVE_TRIGGERS,
    CREATOR_REVEAL_PHRASES,
    MAX_TOKENS,
    TEMPERATURE,
)
from .db.chat_history import save_message, load_history, clear_chat_history

logger = logging.getLogger(__name__)


class GigaChatService:
    """Сервис для взаимодействия с GigaChat с потокобезопасным клиентом."""

    def __init__(self) -> None:
        self._client: GigaChat | None = None
        self._lock = threading.Lock()

    def _create_client(self, max_retries: int = 1) -> GigaChat | None:
        if not settings.gigachat_auth_key:
            logger.error("GIGACHAT_AUTH_KEY не задан — клиент не будет создан.")
            return None
        try:
            client = GigaChat(
                credentials=settings.gigachat_auth_key,
                scope=GIGACHAT_API_PERS,
                verify_ssl_certs=False,
                timeout=settings.gigachat_timeout_seconds,
                max_retries=max_retries,
                retry_backoff_factor=0.3,
                retry_on_status_codes=(429, 500, 502, 503, 504),
            )
            logger.info(
                "GigaChat клиент успешно инициализирован (timeout=%d сек, retries=%d).",
                settings.gigachat_timeout_seconds,
                max_retries,
            )
            return client
        except Exception as e:
            logger.error("Ошибка инициализации клиента GigaChat: %s", e)
            return None

    def get_client(self, max_retries: int = 1) -> GigaChat | None:
        """Возвращает экземпляр клиента GigaChat, создавая его при первом вызове."""
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = self._create_client(max_retries)
        return self._client

    def chat(self, user_id: int, user_text: str) -> str:
        """Отправляет запрос пользователя в GigaChat и возвращает ответ."""
        client = self.get_client()
        if client is None:
            logger.warning("GigaChat клиент не инициализирован — возвращаем заглушку.")
            return random.choice(SILENT_RESPONSES)

        try:
            save_message(user_id, "user", user_text)

            history = load_history(user_id, limit=settings.max_history * 2)
            messages = [
                {"role": "system", "content": build_system_prompt()}
            ] + history

            payload = {
                "model": MODEL,
                "messages": messages,
                "max_tokens": MAX_TOKENS,
                "temperature": TEMPERATURE,
            }

            response = client.chat(payload)

            if not response:
                logger.warning("GigaChat: пустой ответ (None) для user_id=%s", user_id)
                return random.choice(SILENT_RESPONSES)

            choices = getattr(response, "choices", None)
            if not choices or len(choices) == 0:
                logger.warning("GigaChat: ответ без choices для user_id=%s", user_id)
                return random.choice(SILENT_RESPONSES)

            message = getattr(choices[0], "message", None)
            if not message:
                logger.warning("GigaChat: ответ без message для user_id=%s", user_id)
                return random.choice(SILENT_RESPONSES)

            content = getattr(message, "content", None)
            if not content or not content.strip():
                logger.warning("GigaChat: пустой content для user_id=%s", user_id)
                return random.choice(SILENT_RESPONSES)

            answer = content.strip()

            answer_lower = answer.lower()
            if any(trigger in answer_lower for trigger in SENSITIVE_TRIGGERS):
                answer = random.choice(SILENT_RESPONSES)

            if any(phrase in answer_lower for phrase in CREATOR_REVEAL_PHRASES):
                logger.warning(
                    "GigaChat: ответ содержит информацию о создателе — заменяю на заглушку."
                )
                answer = random.choice(SILENT_RESPONSES)

            save_message(user_id, "assistant", answer)
            return answer

        except RateLimitError as e:
            retry_after = getattr(e, "retry_after", None)
            logger.warning("GigaChat: достигнут лимит запросов. Retry-after: %s", retry_after)
            return "Я сейчас слишком занят, много разговоров… Напиши через минутку 🐱"

        except AuthenticationError as e:
            logger.error("GigaChat: ошибка аутентификации: %s", e)
            return "У меня проблемы с доступом к нейросети 😿 Скажи админу!"

        except httpx.ConnectTimeout:
            logger.warning("GigaChat: таймаут соединения для user_id=%s", user_id)
            return "Не могу дозвониться до нейросети… Попробуй чуть позже! 🐾"

        except httpx.ConnectError as e:
            logger.error("GigaChat: ошибка соединения для user_id=%s: %s", user_id, e)
            return "Не могу дозвониться до нейросети… Попробуй чуть позже! 🐾"

        except httpx.ReadTimeout:
            logger.warning("GigaChat: таймаут чтения ответа для user_id=%s", user_id)
            return "Нейросеть думает слишком долго… Давай попозже? 🐱"

        except httpx.TimeoutException as e:
            logger.warning("GigaChat: таймаут для user_id=%s: %s", user_id, e)
            return "Нейросеть думает слишком долго… Давай попозже? 🐱"

        except GigaChatException as e:
            error_str = str(e)
            if "402" in error_str:
                logger.error("GigaChat: закончились токены/квота!")
                return "У меня закончилась квота на нейросеть 😿 Приходи позже!"
            logger.error("GigaChat: ошибка для user_id=%s: %s", user_id, e)
            return random.choice(SILENT_RESPONSES)

        except Exception:
            logger.exception("Непредвиденная ошибка при обработке запроса user_id=%s", user_id)
            return random.choice(SILENT_RESPONSES)


_service = GigaChatService()


def get_chat_response(user_id: int, user_text: str) -> str:
    return _service.chat(user_id, user_text)


def clear_history(user_id: int) -> None:
    """Очищает историю диалога для пользователя в БД."""
    clear_chat_history(user_id)


__all__ = ["GigaChatService", "get_chat_response", "clear_history"]
