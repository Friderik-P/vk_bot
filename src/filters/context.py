# vk_bot/src/filters/context.py
"""Контекстный фильтр: медицина, наркотики, война, психотропы, химия.

Блокирует сообщения, содержащие запрещённые фразы (хрони).
Баны не выдаются — только короткий ответ и лог-запись.
"""

import logging
from pathlib import Path
from typing import Final

import yaml

from .utils import normalize_text, transliterate_to_cyrillic

logger = logging.getLogger(__name__)

# ─── Загрузка конфигурации из YAML ─────────────────────────────
_CONFIG_PATH = Path(__file__).resolve().parent / "context_config.yaml"

with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
    _config = yaml.safe_load(_f)

CONTEXT_PHRASES: Final[frozenset[str]] = frozenset(_config["context_phrases"])
CONTEXT_RESPONSES: Final[tuple[str, ...]] = tuple(_config["context_responses"])


def is_context_blocked(text: str) -> bool:
    """
    Проверяет, содержит ли текст запрещённые контекстные фразы.

    Проверяет как исходный нормализованный текст, так и его
    транслитерированную версию (латиница → кириллица) для перехвата
    смешанных скриптов.

    При ошибке нормализации — возвращаем False (пропускаем),
    чтобы не блокировать обычные сообщения.
    """
    if not text:
        return False

    try:
        normalized = normalize_text(text)
    except Exception:
        logger.exception("Контекстный фильтр: ошибка нормализации текста — пропускаю")
        return False

    if not normalized:
        return False

    # Проверяем оба варианта: исходный и транслитерированный (лат→кир)
    for check_text in (normalized, transliterate_to_cyrillic(normalized)):
        for phrase in CONTEXT_PHRASES:
            if phrase in check_text:
                return True
            # Учёт обхода без пробелов (например, "наркотики" → "наркотики")
            compact_phrase = phrase.replace(" ", "")
            if compact_phrase and compact_phrase in check_text.replace(" ", ""):
                return True

    return False