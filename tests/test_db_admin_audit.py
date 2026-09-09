# tests/test_db_admin_audit.py
"""Тесты audit log администраторов."""

import pytest


class TestAdminAudit:
    """Тесты модуля admin_audit."""

    def test_log_and_get(self, db: Path) -> None:
        """Запись и чтение audit log."""
        from src.db.admin_audit import log_admin_action, get_admin_audit

        log_admin_action(admin_id=123, command="/health", peer_id=456)
        log_admin_action(admin_id=123, command="/stats", peer_id=456)

        records = get_admin_audit(limit=10)

        assert len(records) == 2
        assert records[0]["admin_id"] == 123
        assert records[0]["command"] == "/stats"
        assert records[0]["peer_id"] == 456
        assert records[1]["command"] == "/health"

    def test_filter_by_admin(self, db: Path) -> None:
        """Фильтрация по admin_id работает."""
        from src.db.admin_audit import log_admin_action, get_admin_audit

        log_admin_action(admin_id=1, command="/health", peer_id=100)
        log_admin_action(admin_id=2, command="/stats", peer_id=200)

        records = get_admin_audit(admin_id=1, limit=10)

        assert len(records) == 1
        assert records[0]["admin_id"] == 1
        assert records[0]["command"] == "/health"

    def test_limit(self, db: Path) -> None:
        """limit ограничивает количество возвращаемых записей."""
        from src.db.admin_audit import log_admin_action, get_admin_audit

        for i in range(10):
            log_admin_action(admin_id=1, command=f"/cmd{i}", peer_id=100)

        records = get_admin_audit(admin_id=1, limit=3)
        assert len(records) == 3
        assert records[0]["command"] == "/cmd9"
        assert records[1]["command"] == "/cmd8"
        assert records[2]["command"] == "/cmd7"
