# vk_bot/src/handlers/message.py
"""Обработка входящих текстовых сообщений пользователя."""

import random
import logging

from ..keyboards import get_main_menu_keyboard
from ..chat import get_chat_response, clear_history
from ..config import GIGACHAT_AUTH_KEY, MAX_MESSAGE_LENGTH
from ..filters import is_adult_content, ADULT_RESPONSES, is_context_blocked, CONTEXT_RESPONSES
from ..db import is_adult_banned, record_adult_violation, increment_stats
from .utils import normalize_text_for_triggers

logger = logging.getLogger(__name__)

SIMPLE_RESPONSES = [
    "Мяу! Расскажи ещё 🐱",
    "Интересно… продолжай! 🐾",
    "Я тут, слушаю тебя!",
    "Хм, любопытно! Что дальше?",
    "Пиши ещё, мне интересно! 🐱",
]

SIMPLE_TRIGGERS = {
    "привет", "хай", "здравствуй", "ку", "йо",
    "пока", "досвидания", "спасибо", "благодарю",
    "какдела", "чкокак", "чтонового",
}


def _is_simple_trigger(text: str) -> bool:
    normalized = normalize_text_for_triggers(text)
    return normalized in SIMPLE_TRIGGERS


def handle_message(server, event) -> bool:
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
    if len(text) > MAX_MESSAGE_LENGTH:
        server.send_message(
            peer_id,
            f"😿 Слишком длинное сообщение! Лимит — {MAX_MESSAGE_LENGTH} символов. "
            "Попробуй разбить его на части или сократить.",
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
        server.send_message(peer_id, "🐱 Мяу! Вот котик.", keyboard=keyboard)
        return True

    if text_lower in ("помощь", "/help"):
        server.send_message(
            peer_id,
            "Я умею:\n"
            "🐱 Мяукать\n"
            "💬 Болтать на любые темы\n"
            "🔄 /reset — сбросить диалог\n"
            "ℹ️ Контакты — связь со мной\n\n"
            "Просто напиши мне что угодно!",
            keyboard=keyboard,
        )
        return True

    if text_lower == "контакты":
        server.send_message(
            peer_id,
            "Связаться со мной можно через личные сообщения группы. Я всегда на связи! 🐾",
            keyboard=keyboard,
        )
        return True

    if text_lower == "/reset":
        clear_history(from_id)
        server.send_message(
            peer_id,
            "🔄 Контекст диалога сброшен! Начинаем с чистого листа.",
            keyboard=keyboard,
        )
        return True

    # 3. Проверка бана за 18+ контент (до фильтра и LLM)
    if is_adult_banned(from_id):
        server.send_message(
            peer_id,
            "Мяу… ты забанен на 5 минут за 18+ контент. Отдыхай! 🐱",
            keyboard=keyboard,
        )
        logger.info("Заблокировано сообщение от user_id=%d — бан 18+ активен", from_id)
        return True

    # 4. Простые триггеры (без LLM)
    if _is_simple_trigger(text):
        response = random.choice(SIMPLE_RESPONSES)
        server.send_message(peer_id, response, keyboard=keyboard)
        return True

    # 5. Фильтр 18+ — до запроса к LLM
    if is_adult_content(text):
        banned = record_adult_violation(from_id)
        if banned:
            response = "Мяу… ты забанен на 5 минут за 18+ контент. Отдыхай! 🐱"
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
    if not GIGACHAT_AUTH_KEY:
        server.send_message(
            peer_id,
            "Сейчас я не могу поболтать через нейросеть (нет ключа), "
            "но давай просто поболтаем! Напиши «мяу» или «помощь».",
            keyboard=keyboard,
        )
        return True

    try:
        answer = get_chat_response(from_id, text)
        if not answer:
            answer = "Кажется, нейросеть не ответила. Попробуй ещё раз!"
        increment_stats(llm=1)
    except Exception:
        logger.exception("Ошибка при вызове get_chat_response для user_id=%d", from_id)
        increment_stats(errors=1)
        answer = "Что-то пошло не так… Попробуй чуть позже!"

    server.send_message(peer_id, answer, keyboard=keyboard)
    return True
