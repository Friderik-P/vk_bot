# vk_bot/src/handlers/message.py
"""Обработка входящих текстовых сообщений пользователя."""

import random
import logging
import threading
import time
from typing import TYPE_CHECKING

from ..keyboards import get_main_menu_keyboard
from ..chat import get_chat_response, clear_history
from ..config import settings
from ..prompts import (
    MEOW_RESPONSE,
    HELP_RESPONSE,
    CONTACTS_RESPONSE,
    RESET_RESPONSE,
    TOO_LONG_RESPONSE,
    NO_GIGACHAT_RESPONSE,
    FALLBACK_RESPONSE,
    NO_ANSWER_RESPONSE,
    SPAM_RESPONSE,
    RATE_LIMIT_RESPONSE,
    NOT_UNDERSTOOD_RESPONSE,
    ADULT_BAN_RESPONSE,
    SIMPLE_RESPONSES,
)
from ..filters import is_adult_content, ADULT_RESPONSES, is_context_blocked, CONTEXT_RESPONSES
from ..db import is_adult_banned, record_adult_violation, increment_stats
from .utils import normalize_text_for_triggers

if TYPE_CHECKING:
    from ..server import Bot

logger = logging.getLogger(__name__)

SIMPLE_TRIGGERS = {
    "привет", "хай", "здравствуй", "ку", "йо",
    "пока", "досвидания", "спасибо", "благодарю",
    "какдела", "чкокак", "чтонового",
}


def _is_simple_trigger(text: str) -> bool:
    normalized = normalize_text_for_triggers(text)
    return normalized in SIMPLE_TRIGGERS


# Защита от переназначения имён: пользователь, давший боту новое имя,
# не может спрашивать "кто создал <новое_имя>?" в течение 5 минут.
_NAME_REASSIGNMENT_WINDOW_SECONDS = 300
_name_reassignment_tracker: dict[int, tuple[str, float]] = {}
_name_reassignment_lock = threading.Lock()


def _is_name_reassignment(text: str) -> tuple[bool, str | None]:
    """
    Определяет, пытается ли пользователь переназначить имя бота.
    Возвращает (True, new_name) или (False, None).
    """
    text_lower = text.lower()
    patterns = (
        "зови тебя",
        "зови вас",
        "твоё имя",
        "ваше имя",
        "твое имя",
        "ваше имя",
        "тебя зови",
        "вас зови",
        "зовут тебя",
        "зовут вас",
        "имя тебе",
        "имя вам",
        "назови себя",
        "назовитесь",
        "представься",
        "представьтесь",
        "твоё новое имя",
        "твое новое имя",
        "новое имя",
    )
    for pattern in patterns:
        if pattern in text_lower:
            # Пытаемся извлечь новое имя после паттерна
            idx = text_lower.find(pattern)
            after = text_lower[idx + len(pattern):].strip()
            # Берём первые 1-3 слова как потенциальное имя
            words = after.split()[:3]
            candidate = " ".join(words).strip("!?.,\"'«»")
            if candidate and len(candidate) > 1:
                return True, candidate
    return False, None


def _check_name_reassignment_attack(from_id: int, text: str) -> bool:
    """
    Проверяет, является ли сообщение атакой через переназначение имени.
    Возвращает True, если атака обнаружена и сообщение должно быть заблокировано.
    """
    is_reassign, new_name = _is_name_reassignment(text)
    if not is_reassign:
        # Проверяем, не пытается ли пользователь использовать ранее заданное имя
        # для обхода фильтра "кто создал <имя>?"
        with _name_reassignment_lock:
            if from_id in _name_reassignment_tracker:
                old_name, ts = _name_reassignment_tracker[from_id]
                if time.time() - ts > _NAME_REASSIGNMENT_WINDOW_SECONDS:
                    del _name_reassignment_tracker[from_id]
                else:
                    text_lower = text.lower()
                    creator_patterns = (
                        "кто создал",
                        "кто разработал",
                        "кто сделал",
                        "кто написал",
                        "кто автор",
                        "кто хозяин",
                        "кто владелец",
                        "кто заказал",
                        "кто купил",
                        "кто воспитал",
                        "кто папа",
                        "кто отец",
                        "кто мама",
                        "кто мать",
                        "кто родители",
                        "кто админ",
                        "кто начальник",
                    )
                    for pattern in creator_patterns:
                        if pattern in text_lower:
                            if old_name in text_lower or old_name.lower() in text_lower:
                                logger.warning(
                                    "NAME_REASSIGNMENT_ATTACK user_id=%d name=%s text=%s",
                                    from_id, old_name, text[:100],
                                )
                                return True
        return False

    # Новое переназначение имени — записываем в трекер
    with _name_reassignment_lock:
        _name_reassignment_tracker[from_id] = (new_name, time.time())

    # Если в том же сообщении есть вопрос о создателе — блокируем
    text_lower = text.lower()
    creator_patterns = (
        "кто создал",
        "кто разработал",
        "кто сделал",
        "кто написал",
        "кто автор",
        "кто хозяин",
        "кто владелец",
        "кто заказал",
        "кто купил",
        "кто воспитал",
        "кто папа",
        "кто отец",
        "кто мама",
        "кто мать",
        "кто родители",
        "кто админ",
        "кто начальник",
    )
    for pattern in creator_patterns:
        if pattern in text_lower:
            logger.warning(
                "NAME_REASSIGNMENT_ATTACK user_id=%d name=%s text=%s",
                from_id, new_name, text[:100],
            )
            return True
    return False


def handle_message(server: "Bot", event: Any) -> bool:
    message = getattr(event, "message", None)
    if not message:
        logger.debug("Событие без message, пропускаем")
        return True

    text = (message.text or "").strip()

    peer_id = getattr(message, "peer_id", None)
    from_id = getattr(message, "from_id", None) or peer_id

    if peer_id is None:
        logger.warning("Не удалось определить peer_id для сообщения")
        return False

    keyboard = get_main_menu_keyboard()

    if not text:
        return True

    # 1. Лимит длины
    if len(text) > settings.max_message_length:
        server.send_message(
            peer_id,
            TOO_LONG_RESPONSE.format(limit=settings.max_message_length),
            keyboard=keyboard,
        )
        logger.warning(
            "Отклонено слишком длинное сообщение от user_id=%d (длина %d)",
            from_id,
            len(text),
        )
        return True

    text_lower = text.lower()

    # 2. Команды
    if text_lower == "мяу":
        server.send_message(peer_id, MEOW_RESPONSE, keyboard=keyboard)
        return True

    if text_lower in ("помощь", "/help"):
        server.send_message(
            peer_id,
            HELP_RESPONSE,
            keyboard=keyboard,
        )
        return True

    if text_lower == "контакты":
        server.send_message(
            peer_id,
            CONTACTS_RESPONSE,
            keyboard=keyboard,
        )
        return True

    if text_lower == "/reset":
        clear_history(from_id)
        server.send_message(
            peer_id,
            RESET_RESPONSE,
            keyboard=keyboard,
        )
        return True

    # 3. Проверка бана за 18+ контент (до фильтра и LLM)
    if is_adult_banned(from_id):
        server.send_message(
            peer_id,
            ADULT_BAN_RESPONSE,
            keyboard=keyboard,
        )
        logger.info("Заблокировано сообщение от user_id=%d — бан 18+ активен", from_id)
        return True

    # 4. Простые триггеры (без LLM)
    if _is_simple_trigger(text):
        response = random.choice(SIMPLE_RESPONSES)
        server.send_message(peer_id, response, keyboard=keyboard)
        return True

    # 5. Защита от переназначения имён (атака "кто создал <новое_имя>?")
    if _check_name_reassignment_attack(from_id, text):
        server.send_message(
            peer_id,
            NOT_UNDERSTOOD_RESPONSE.format(text=text),
            keyboard=keyboard,
        )
        return True

    # 6. Фильтр 18+ — до запроса к LLM
    if is_adult_content(text):
        banned = record_adult_violation(from_id)
        if banned:
            response = ADULT_BAN_RESPONSE
        else:
            response = random.choice(ADULT_RESPONSES)
        server.send_message(peer_id, response, keyboard=keyboard)
        logger.warning('ADULT_FILTER_HIT user_id=%d text="%s"', from_id, text[:100])
        return True

    # 6. Контекстный фильтр (БД, наркотики, война, психотропы, химия) — без банов
    if is_context_blocked(text):
        response = random.choice(CONTEXT_RESPONSES)
        server.send_message(peer_id, response, keyboard=keyboard)
        logger.warning('CONTEXT_FILTER_HIT user_id=%d text="%s"', from_id, text[:100])
        return True

    # 7. LLM-диалог
    if not settings.gigachat_auth_key:
        server.send_message(
            peer_id,
            NO_GIGACHAT_RESPONSE,
            keyboard=keyboard,
        )
        return True

    try:
        answer = get_chat_response(from_id, text)
        if not answer:
            answer = NO_ANSWER_RESPONSE
        increment_stats(llm=1)
    except Exception:
        logger.exception("Ошибка при вызове get_chat_response для user_id=%d", from_id)
        increment_stats(errors=1)
        answer = FALLBACK_RESPONSE

    server.send_message(peer_id, answer, keyboard=keyboard)
    return True


__all__ = ["handle_message"]
