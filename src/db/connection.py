# vk_bot/src/db/connection.py
"""Пул SQLite-соединений и ретраи при блокировках."""

import logging
import random
import sqlite3
import threading
import time
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Callable

from ..config import settings
from ..constants import (
    DB_CONNECTION_POOL_MAX_SIZE,
    DB_RETRY_MAX_ATTEMPTS,
    DB_RETRY_BASE_DELAY,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = DB_RETRY_MAX_ATTEMPTS
RETRY_DELAY = DB_RETRY_BASE_DELAY
MAX_POOL_SIZE = DB_CONNECTION_POOL_MAX_SIZE

_pool: ConnectionPool | None = None


def get_db_path() -> Path:
    """Возвращает абсолютный путь к файлу БД (лениво, после загрузки конфига)."""
    return Path(settings.db_file).resolve()


class _PooledConnection(AbstractContextManager):
    """Контекстный менеджер, возвращающий соединение в пул после использования."""

    def __init__(self, pool: "ConnectionPool", conn: sqlite3.Connection):
        self.pool = pool
        self.conn = conn

    def __enter__(self) -> sqlite3.Connection:
        return self.conn

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if exc_type is not None:
            try:
                self.conn.rollback()
            except Exception:
                pass
        self.pool.put(self.conn)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.conn, name)


class ConnectionPool:
    """Ограниченный пул SQLite-соединений для многопоточной работы."""

    def __init__(self, db_path: Path, max_size: int = MAX_POOL_SIZE):
        self.db_path = db_path
        self.max_size = max_size
        self._available: list[sqlite3.Connection] = []
        self._in_use: set[sqlite3.Connection] = set()
        self._created = 0
        self._condition = threading.Condition()

    def _create(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=10.0,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        _apply_pragmas(conn)
        return conn

    def get(self) -> _PooledConnection:
        """Возвращает соединение из пула, создавая новое при необходимости."""
        with self._condition:
            while True:
                if self._available:
                    conn = self._available.pop()
                    self._in_use.add(conn)
                    return _PooledConnection(self, conn)
                if self._created < self.max_size:
                    conn = self._create()
                    self._created += 1
                    self._in_use.add(conn)
                    logger.debug(
                        "Создано SQLite-соединение (пул: %d/%d)",
                        self._created,
                        self.max_size,
                    )
                    return _PooledConnection(self, conn)
                self._condition.wait()

    def put(self, conn: sqlite3.Connection) -> None:
        """Возвращает соединение в пул и будит ожидающих потоков."""
        with self._condition:
            self._in_use.discard(conn)
            self._available.append(conn)
            self._condition.notify_all()

    def close_all(self) -> None:
        """Закрывает все соединения пула."""
        with self._condition:
            connections = list(self._in_use) + list(self._available)
            self._in_use.clear()
            self._available.clear()
            self._condition.notify_all()

        closed = 0
        for conn in connections:
            try:
                conn.close()
                closed += 1
            except Exception:
                pass

        logger.info("Все SQLite-соединения закрыты (%d/%d шт.).", closed, len(connections))


def get_pool() -> ConnectionPool:
    """Возвращает пул соединений (ленивая инициализация)."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(get_db_path())
    return _pool


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """Применяет PRAGMA-настройки для оптимизации параллельной работы."""
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA cache_size=-6400")  # ~6 МБ кеш
    except sqlite3.DatabaseError as e:
        logger.warning("Не удалось применить PRAGMA-настройки: %s", e)


def _is_connection_valid(conn: sqlite3.Connection) -> bool:
    """Быстрая проверка: отвечает ли соединение."""
    try:
        conn.execute("SELECT 1")
        return True
    except Exception:
        return False


def get_connection() -> _PooledConnection:
    """Возвращает соединение из пула с контекстным менеджером."""
    return get_pool().get()


def close_connection() -> None:
    """Закрывает все соединения пула. Оставлено для обратной совместимости."""
    get_pool().close_all()


def close_all_connections() -> None:
    """Закрывает все соединения пула."""
    get_pool().close_all()


def retry_on_lock(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """
    Выполняет функцию fn с ретраем при sqlite3.OperationalError ('locked' или 'busy').
    Задержка удваивается на каждой попытке + случайный джиттер (до 30%):
    ~0.5с → ~1.0с → ~2.0с. Джиттер предотвращает thundering herd.
    """
    delay = RETRY_DELAY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except sqlite3.OperationalError as e:
            error_str = str(e).lower()
            is_lock_error = "locked" in error_str or "busy" in error_str

            if is_lock_error and attempt < MAX_RETRIES:
                jitter = delay * random.uniform(0, 0.3)
                total_wait = delay + jitter
                logger.warning(
                    "БД заблокирована (попытка %d/%d), жду %.2f с...",
                    attempt, MAX_RETRIES, total_wait,
                )
                time.sleep(total_wait)
                delay *= 2
            else:
                raise

    # Недостижимо при MAX_RETRIES >= 1, но защита от MAX_RETRIES = 0
    raise sqlite3.OperationalError("retry_on_lock: MAX_RETRIES исчерпаны")

__all__ = [
    "get_connection",
    "close_connection",
    "close_all_connections",
    "retry_on_lock",
    "ConnectionPool",
    "get_db_path",
    "get_pool",
]
