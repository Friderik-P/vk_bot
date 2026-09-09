# tests/test_filters_spam.py
"""Тесты спам-фильтра."""

import pytest

from src.filters.spam import analyze_message_for_spam


class TestAnalyzeMessageForSpam:
    """Тесты analyze_message_for_spam."""

    def test_clean_message(self) -> None:
        is_spam, reason = analyze_message_for_spam("привет, как дела?")
        assert is_spam is False
        assert reason is None

    def test_caps_spam(self) -> None:
        is_spam, reason = analyze_message_for_spam("ПРИВЕТ КАК ДЕЛА БОТ")
        assert is_spam is True
        assert reason == "caps"

    def test_emoji_spam(self) -> None:
        text = "привет" + "😀" * 10
        is_spam, reason = analyze_message_for_spam(text)
        assert is_spam is True
        assert reason == "emoji_spam"

    def test_short_message_not_spam(self) -> None:
        is_spam, reason = analyze_message_for_spam("ку")
        assert is_spam is False

    def test_empty_message(self) -> None:
        is_spam, reason = analyze_message_for_spam("")
        assert is_spam is False
