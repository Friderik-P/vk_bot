# vk_bot/src/db/connection.py
"""Управление thread-local соединениями SQLite и ретраи при блокировках."""

import sqlite3
import threading
import time
import random
from pathlib import Path
from typing import Any, Callable
import logging

from ..config import DB_FILE

logger = logging.getLogger(__name__)

# Абсолютный путь к БД — защита от разных рабочих директорий (systemd, cron)
DB_PATH = Path(DB_FILE).resolve()

_local = threading.local()
# Хранилище созданных соединений: id(conn) -> conn (для O(1) удаления)
_all_connections: dict[int, sqlite3.Connection] = {}
_all_lock = threading.Lock()

MAX_RETRIES = 3
RETRY_DELAY = 0.5  # базовая задержка, удваивается + джиттер


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


def get_connection() -> sqlite3.Connection:
    """
    Возвращает thread-local соединение.
    Создаётся один раз на поток, переиспользуется при последующих вызовах.
    Если соединение стало невалидным — пересоздаёт его.
    """
    conn = getattr(_local, "conn", None)

    if conn is not None:
        if _is_connection_valid(conn):
            return conn
        # Соединение умер — очищаем
        logger.warning("SQLite-соединение стало невалидным, пересоздаю (поток %s)",
                       threading.current_thread().name)
        try:
            conn.close()
        except Exception:
            pass
        with _all_lock:
            _all_connections.pop(id(conn), None)
        _local.conn = None

    # Создаём новое
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    _local.conn = conn

    with _all_lock:
        _all_connections[id(conn)] = conn

    logger.debug(
        "Создано SQLite-соединение для потока %s",
        threading.current_thread().name,
    )
    return _local.conn


def close_connection() -> None:
    """Закрывает соединение текущего потока. Вызывать при завершении."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        with _all_lock:
            _all_connections.pop(id(conn), None)
        _local.conn = None
        logger.debug(
            "SQLite-соединение закрыто для потока %s",
            threading.current_thread().name,
        )


def close_all_connections() -> None:
    """
    Закрывает все активные соединения во всех потоках.
    Берёт слепок под блокировкой, закрывает без блокировки —
    чтобы не держать лок при потенциально долгом .close().
    """
    with _all_lock:
        connections = list(_all_connections.values())
        _all_connections.clear()

    closed = 0
    for conn in connections:
        try:
            conn.close()
            closed += 1
        except Exception:
            pass

    logger.info("Все SQLite-соединения закрыты (%d/%d шт.).", closed, len(connections))


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
