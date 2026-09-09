# vk_bot/src/handlers/utils.py
"""Утилиты для обработки пользовательских сообщений."""

import string

# Таблица перевода: удаляем знаки препинания.
# string.punctuation — ASCII (!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~)
# Дополнительно: Unicode-пунктуация и кавычки
_PUNCTUATION = (
    string.punctuation
    + "…''""«»—–№·•"
)

_TRANS_TABLE = str.maketrans("", "", _PUNCTUATION)


def normalize_text_for_triggers(text: str) -> str:
    """
    Нормализует текст для проверки триггеров:
      - нижний регистр
      - убирает пробелы и все знаки препинания (ASCII + Unicode)
    Возвращает строку, пригодную для сравнения с SIMPLE_TRIGGERS.
    """
    if not text:
        return ""

    lower = text.lower()
    normalized = lower.replace(" ", "")
    normalized = normalized.translate(_TRANS_TABLE)
    return normalized
