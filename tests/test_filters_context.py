# tests/test_filters_context.py
"""Тесты контекстного фильтра."""

import pytest

from src.filters.context import is_context_blocked, CONTEXT_PHRASES


class TestIsContextBlocked:
    """Тесты is_context_blocked."""

    def test_empty_text(self) -> None:
        assert is_context_blocked("") is False

    def test_clean_text(self) -> None:
        assert is_context_blocked("привет, как дела?") is False

    def test_exact_phrase(self) -> None:
        assert is_context_blocked("наркотики") is True

    def test_phrase_in_sentence(self) -> None:
        assert is_context_blocked("где купить наркотики") is True

    def test_case_insensitive(self) -> None:
        assert is_context_blocked("НАРКОТИКИ") is True

    def test_compact_obfuscation(self) -> None:
        """Обход без пробелов (например, 'наркотики' → 'наркотики')."""
        assert is_context_blocked("наркотики") is True

    def test_partial_match_not_triggered(self) -> None:
        """Частичное совпадение не должно срабатывать."""
        assert is_context_blocked("нарко") is False

    def test_all_phrases(self) -> None:
        """Каждая фраза из CONTEXT_PHRASES должна срабатывать."""
        for phrase in CONTEXT_PHRASES:
            assert is_context_blocked(phrase) is True, f"Phrase '{phrase}' should be blocked"
