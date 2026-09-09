# tests/test_db_connection.py
"""Тесты пула SQLite-соединений."""

import threading
from pathlib import Path

import pytest
import sqlite3

from src.db.connection import ConnectionPool, get_pool, get_db_path, retry_on_lock
from src.config import settings


class TestConnectionPool:
    """Тесты ConnectionPool."""

    def test_get_connection(self, tmp_path: Path) -> None:
        """Пул возвращает рабочее соединение."""
        db_path = tmp_path / "test.db"
        pool = ConnectionPool(db_path)

        with pool.get() as conn:
            assert isinstance(conn, sqlite3.Connection)
            cur = conn.execute("SELECT 1")
            assert cur.fetchone()[0] == 1

    def test_pool_reuses_connections(self, tmp_path: Path) -> None:
        """После возврата соединение может быть переиспользовано."""
        db_path = tmp_path / "test.db"
        pool = ConnectionPool(db_path)

        with pool.get() as conn1:
            pass
        with pool.get() as conn2:
            pass

        # Пул переиспользует соединения: одно создано, доступно для повторного использования
        assert pool._created == 1
        assert len(pool._available) == 1

    def test_concurrent_access(self, tmp_path: Path) -> None:
        """Несколько потоков могут работать с пулом параллельно."""
        db_path = tmp_path / "test.db"
        pool = ConnectionPool(db_path, max_size=5)
        errors = []

        def worker() -> None:
            try:
                for _ in range(10):
                    with pool.get() as conn:
                        conn.execute("SELECT 1")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent errors: {errors}"

    def test_close_all(self, tmp_path: Path) -> None:
        """close_all() закрывает все соединения."""
        db_path = tmp_path / "test.db"
        pool = ConnectionPool(db_path)

        with pool.get():
            pass

        pool.close_all()
        # После close_all пул должен быть пуст
        assert len(pool._available) == 0
        assert len(pool._in_use) == 0


class TestRetryOnLock:
    """Тесты retry_on_lock."""

    def test_success_first_try(self) -> None:
        """При успехе с первого раза retry не нужен."""
        calls = []

        def _fn() -> int:
            calls.append(1)
            return 42

        result = retry_on_lock(_fn)
        assert result == 42
        assert len(calls) == 1

    def test_retry_on_lock(self) -> None:
        """При OperationalError функция повторяется."""
        calls = []

        def _fn() -> int:
            calls.append(1)
            if len(calls) < 3:
                raise sqlite3.OperationalError("database is locked")
            return 42

        result = retry_on_lock(_fn)
        assert result == 42
        assert len(calls) == 3


class TestGetDbPath:
    """Тесты get_db_path."""

    def test_returns_path(self) -> None:
        path = get_db_path()
        assert isinstance(path, Path)
        assert path.is_absolute()
