# vk_bot/src/filters/adult.py
"""Фильтр 18+ контента. Срабатывает до запроса к LLM — экономит токены."""

import re
import logging
from pathlib import Path
from typing import Final

import yaml

from .utils import normalize_text, transliterate_to_cyrillic

logger = logging.getLogger(__name__)

# ─── Загрузка конфигурации из YAML ─────────────────────────────
_CONFIG_PATH = Path(__file__).resolve().parent / "adult_config.yaml"

with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
    _config = yaml.safe_load(_f)

ADULT_KEYWORDS: Final[frozenset[str]] = frozenset(_config["adult_keywords"])
ADULT_KEYWORDS_SOFT: Final[frozenset[str]] = frozenset(_config["adult_keywords_soft"])
ADULT_PHRASES: Final[frozenset[str]] = frozenset(_config["adult_phrases"])
ADULT_RESPONSES: Final[tuple[str, ...]] = tuple(_config["adult_responses"])

ADULT_REGEX_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(p, re.IGNORECASE) for p in _config["adult_regex_patterns"]
]

_ADULT_PREFIXES: Final[frozenset[str]] = frozenset(_config["adult_prefixes"])


def is_adult_content(text: str) -> bool:
    """
    Проверяет, содержит ли текст 18+ контент (жёсткий уровень).

    Порядок проверки:
      1. Regex-паттерны (эвфемизмы, сокращения)
      2. Фразы (многословные сочетания) — с учётом обхода без пробелов
      3. Точные совпадения по словам (уровень 1)
      4. Префиксные совпадения (уровень 1)

    Проверяет как исходный нормализованный текст, так и его
    транслитерированную версию (латиница → кириллица) для перехвата
    смешанных скриптов (например, "cекс", "p0rn").

    Мягкие слова (уровень 2) НЕ блокируют — они только логируются
    через is_adult_content_soft(), чтобы не ловить "член сообщества",
    "грудь" в медицине и т.п.

    При ошибке нормализации — возвращаем False (пропускаем),
    чтобы не блокировать обычные сообщения.
    """
    if not text:
        return False

    try:
        normalized = normalize_text(text)
    except Exception:
        logger.exception("18+ фильтр: ошибка нормализации текста — пропускаю")
        return False

    if not normalized:
        return False

    # Проверяем оба варианта: исходный и транслитерированный (лат→кир)
    for check_text in (normalized, transliterate_to_cyrillic(normalized)):
        tokens = set(check_text.split())

        # 1. Regex-паттерны
        for pattern in ADULT_REGEX_PATTERNS:
            if pattern.search(check_text):
                logger.debug("18+ фильтр сработал (regex): %s", pattern.pattern)
                return True

        # 2. Фразы — с учётом обхода без пробелов (например, "хочусекса")
        for phrase in ADULT_PHRASES:
            if phrase in check_text:
                logger.debug("18+ фильтр сработал (фраза): «%s»", phrase)
                return True
            compact_phrase = phrase.replace(" ", "")
            if compact_phrase and compact_phrase in check_text.replace(" ", ""):
                logger.debug("18+ фильтр сработал (фраза без пробелов): «%s»", phrase)
                return True

        # 3. Точные совпадения по словам (уровень 1)
        for token in tokens:
            if token in ADULT_KEYWORDS:
                logger.debug("18+ фильтр сработал (слово): «%s»", token)
                return True

        compact_text = check_text.replace(" ", "")
        if compact_text and compact_text in ADULT_KEYWORDS:
            logger.debug("18+ фильтр сработал (слово без пробелов): «%s»", compact_text)
            return True

        # 4. Префиксные совпадения
        for token in tokens:
            for prefix in _ADULT_PREFIXES:
                if token.startswith(prefix):
                    logger.debug("18+ фильтр сработал (префикс): «%s» в «%s»", prefix, token)
                    return True

        if compact_text:
            for prefix in _ADULT_PREFIXES:
                if compact_text.startswith(prefix):
                    logger.debug("18+ фильтр сработал (префикс без пробелов): «%s» в «%s»", prefix, compact_text)
                    return True

    return False


def is_adult_content_soft(text: str) -> bool:
    """
    Проверяет наличие мягких 18+ слов (уровень 2).
    Не блокирует — только логирует WARNING.
    Используется для мониторинга: "член", "грудь" и т.п. в безобидном контексте.
    """
    if not text:
        return False

    try:
        normalized = normalize_text(text)
    except Exception:
        logger.exception("18+ фильтр: ошибка нормализации текста — пропускаю")
        return False

    if not normalized:
        return False

    tokens = set(normalized.split())
    for token in tokens:
        if token in ADULT_KEYWORDS_SOFT:
            logger.warning(
                "18+ фильтр сработал (мягкое слово): «%s» — возможен ложноположительный результат",
                token,
            )
            return True

    return False


__all__ = [
    "is_adult_content",
    "is_adult_content_soft",
    "ADULT_KEYWORDS",
    "ADULT_KEYWORDS_SOFT",
    "ADULT_PHRASES",
    "ADULT_RESPONSES",
    "ADULT_REGEX_PATTERNS",
]