# tests/test_db_stats.py
"""Тесты статистики бота."""

import pytest


class TestStats:
    """Тесты модуля stats."""

    def test_initial_stats_are_zero(self, db: Path) -> None:
        """При инициализации БД статистика равна нулю."""
        from src.db.stats import get_stats

        stats = get_stats()
        assert stats == {"total_messages": 0, "llm_messages": 0, "errors": 0}

    def test_increment_stats(self, db: Path) -> None:
        """increment_stats() увеличивает счётчики."""
        from src.db.stats import increment_stats, get_stats

        increment_stats(total=5, llm=3, errors=1)
        stats = get_stats()

        assert stats["total_messages"] == 5
        assert stats["llm_messages"] == 3
        assert stats["errors"] == 1

    def test_increment_stats_multiple_calls(self, db: Path) -> None:
        """Несколько вызовов increment_stats() суммируются."""
        from src.db.stats import increment_stats, get_stats

        increment_stats(total=1)
        increment_stats(total=2)
        increment_stats(llm=1)

        stats = get_stats()
        assert stats["total_messages"] == 3
        assert stats["llm_messages"] == 1
        assert stats["errors"] == 0
