# vk_bot/src/filters/spam.py
"""
Текстовый фильтр спама: капс, избыток эмодзи.
Логика банов и лимитов сообщений — в db/spam.py.
"""

from typing import Tuple, Optional
import unicodedata


def _is_emoji(ch: str) -> bool:
    """Проверяет, является ли символ эмодзи (по Unicode-категории)."""
    cat = unicodedata.category(ch)
    if cat == "So":
        return True
    name = unicodedata.name(ch, "")
    return "EMOJI" in name


def analyze_message_for_spam(text: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Простая эвристика для детектирования спама по тексту:
      - капс (более 70% заглавных букв в буквенных символах, длина > 10)
      - избыток эмодзи (> 8 штук, определяются по Unicode-категории)

    Возвращает (True, reason) если это спам, иначе (False, None).
    """
    if not text:
        return False, None

    # --- Капс ---
    letters = [c for c in text if c.isalpha()]
    if letters and len(letters) > 10:
        upper_count = sum(1 for c in letters if c.isupper())
        if upper_count / len(letters) > 0.7:
            return True, "caps"

    # --- Спам эмодзи ---
    # Ранний выход: если не-букв/не-пробелов <= 8,
    # emoji_count гарантированно <= 8 — пропускаем перебор.
    non_text = sum(1 for c in text if not c.isalpha() and not c.isspace())
    if non_text <= 8:
        return False, None

    emoji_count = sum(1 for c in text if _is_emoji(c))

    if emoji_count > 8:
        return True, "emoji_spam"

    return False, None


__all__ = ["analyze_message_for_spam"]
