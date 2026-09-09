import signal
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv


logger = logging.getLogger(__name__)
_shutdown_called = False


def setup_logging():
    """Настраивает логирование: в файлы (в папке logs/) + в консоль."""
    root_logger = logging.getLogger()

    if root_logger.handlers:
        root_logger.handlers.clear()

    root_logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)-8s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)


def setup_file_logging(log_dir: str):
    """Добавляет файловые хендлеры после загрузки конфига."""
    root_logger = logging.getLogger()
    log_path = Path(log_dir)
    try:
        log_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning("Не удалось создать папку логов %s: %s", log_path, e)

    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)-8s | %(message)s"
    )

    try:
        info_handler = RotatingFileHandler(
            log_path / "bot.info.log",
            maxBytes=5_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        info_handler.setLevel(logging.INFO)
        info_handler.setFormatter(formatter)
        root_logger.addHandler(info_handler)
    except OSError as e:
        logger.warning("Не удалось создать info-лог: %s", e)

    try:
        error_handler = RotatingFileHandler(
            log_path / "bot.error.log",
            maxBytes=2_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)
    except OSError as e:
        logger.warning("Не удалось создать error-лог: %s", e)


def _cleanup():
    """Закрывает соединения с БД. Безопасен для повторного вызова."""
    try:
        from src.db import close_all_connections
        close_all_connections()
        logger.info("Соединения с БД успешно закрыты.")
    except Exception as e:
        logger.error("Ошибка при закрытии соединений с БД: %s", e)


def _shutdown(signum=None, frame=None):
    """
    Обработчик сигналов завершения — чистый выход без traceback.
    Защита от повторного вызова через _shutdown_called.
    """
    global _shutdown_called
    if _shutdown_called:
        return
    _shutdown_called = True

    if signum is not None:
        try:
            sig_name = signal.Signals(signum).name
        except ValueError:
            sig_name = f"сигнал {signum}"
        logger.info("Получен сигнал %s. Останавливаюсь... Мяу 🐱", sig_name)

    _cleanup()
    sys.exit(0)


def main():
    BASE_DIR = Path(__file__).resolve().parent
    load_dotenv(BASE_DIR / ".env")

    setup_logging()

    try:
        from src.config import VK_API_TOKEN, VK_GROUP_ID, LOG_DIR, DB_FILE, SERVER_NAME
        from src.server import Server
        from src.db import init_db

        setup_file_logging(LOG_DIR)

        logger.info("Инициализация базы данных (%s)...", DB_FILE)
        init_db()

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        logger.info("Запуск VK-бота (Server)...")
        bot = Server(VK_API_TOKEN, VK_GROUP_ID, server_name=SERVER_NAME)
        bot.start()

        logger.info("Бот завершил работу. Мяу! 🐱")
    except RuntimeError as e:
        logger.critical("Ошибка конфигурации: %s", e, exc_info=True)
        _cleanup()
        sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:
        logger.critical("Непредвиденная ошибка при старте: %s", e, exc_info=True)
        _cleanup()
        sys.exit(1)
    finally:
        _cleanup()


if __name__ == "__main__":
    main()
