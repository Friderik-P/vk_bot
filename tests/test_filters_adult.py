# tests/test_filters_adult.py
"""Тесты 18+ фильтра."""

import pytest

from src.filters.adult import is_adult_content, is_adult_content_soft, ADULT_KEYWORDS, ADULT_PHRASES


class TestIsAdultContent:
    """Тесты is_adult_content."""

    def test_empty_text(self) -> None:
        assert is_adult_content("") is False

    def test_clean_text(self) -> None:
        assert is_adult_content("привет, как дела?") is False

    def test_exact_keyword(self) -> None:
        assert is_adult_content("порно") is True

    def test_keyword_in_phrase(self) -> None:
        assert is_adult_content("смотри порно видео") is True

    def test_phrase_match(self) -> None:
        assert is_adult_content("порно секс") is True

    def test_soft_keyword_not_triggered(self) -> None:
        """Мягкие слова не должны триггерить is_adult_content."""
        assert is_adult_content("член") is False

    def test_case_insensitive(self) -> None:
        assert is_adult_content("ПорНо") is True

    def test_obfuscation(self) -> None:
        """Обфускация через пробелы/дублирование не должна срабатывать."""
        assert is_adult_content("п о р н о") is False

    def test_prefix_match(self) -> None:
        """Префиксные совпадения для слов из ADULT_KEYWORDS."""
        # Порноxxx должно сработать, если есть префикс "порно"
        assert is_adult_content("порноhub") is True


class TestIsAdultContentSoft:
    """Тесты is_adult_content_soft."""

    def test_soft_keyword_triggered(self) -> None:
        assert is_adult_content_soft("член") is True

    def test_soft_keyword_not_in_clean(self) -> None:
        assert is_adult_content_soft("привет") is False
