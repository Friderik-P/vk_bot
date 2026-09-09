# vk_bot/src/server.py
"""VK Long Poll сервер: маршрутизация сообщений, антиспам, админ-команды."""

import logging
import os
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

import requests
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
from vk_api.exceptions import ApiError

from .config import settings
from .constants import (
    VK_ERROR_USER_BLOCKED,
    VK_ERROR_MSG_TOO_LONG,
    VK_ERROR_CHAT_NOT_FOUND,
    VK_ERROR_RATE_LIMIT,
    SCHEDULER_DELAY_SECONDS,
    SCHEDULER_HEALTH_INTERVAL_MINUTES,
)
from .db import (
    load_peer_ids,
    add_peer_id,
    mark_user_blocked,
    check_ratelimit,
    is_spam_banned,
    ban_for_spam,
    get_stats,
    increment_stats,
    log_admin_action,
)
from .db.connection import close_all_connections
from .filters.spam import analyze_message_for_spam
from .keyboards.main_menu import get_main_menu_keyboard
from .keyboards.inline import get_admin_help_inline_keyboard
from .prompts import (
    RATE_LIMIT_RESPONSE,
    SPAM_RESPONSE,
    NOT_UNDERSTOOD_RESPONSE,
    ADMIN_HELP_RESPONSE,
    HELP_RESPONSE,
    STATS_RESPONSE,
)
from .services.health import check_gigachat_manual
from .admins import get_admins, add_admin, remove_admin
from .handlers import handle_message, handle_callback
from .utils.notify import notify_admins

logger = logging.getLogger(__name__)


@runtime_checkable
class Bot(Protocol):
    """Протокол для бота: минимальный интерфейс для хендлеров."""

    def send_message(self, peer_id: int | None, message: str, keyboard: str | None = None) -> None: ...

    @property
    def vk_api(self) -> Any: ...

    @property
    def chat_client(self) -> Any: ...

    def get_peer_ids(self) -> set[int]: ...

    def request_restart(self) -> None: ...

    @property
    def shutdown_event(self) -> Optional[threading.Event]: ...


class AdminCommandHandler:
    """Обработчик админ-команд."""

    def __init__(self, bot: Bot, shutdown_event: Optional[threading.Event] = None) -> None:
        self.bot = bot
        self._shutdown_event = shutdown_event

    def handle(self, from_id: int, peer_id: int, text: str) -> bool:
        """Возвращает True, если команда обработана."""
        if from_id not in get_admins():
            return False

        # /health
        if text.lower().startswith("/health"):
            logger.info("ADMIN_CMD /health user_id=%d peer_id=%s", from_id, peer_id)
            log_admin_action(from_id, "/health", peer_id)
            if self.bot.chat_client is None:
                self.bot.send_message(peer_id, "❌ GigaChat-клиент не инициализирован.")
            else:
                report = check_gigachat_manual(self.bot.chat_client)
                self.bot.send_message(peer_id, report)
            return True

        # /help
        if text.lower() in ("/help", "помощь"):
            logger.info("ADMIN_CMD /help user_id=%d peer_id=%s", from_id, peer_id)
            log_admin_action(from_id, "/help", peer_id)
            self.bot.send_message(
                peer_id,
                HELP_RESPONSE,
                keyboard=get_main_menu_keyboard(),
            )
            self.bot.send_message(peer_id, ADMIN_HELP_RESPONSE, keyboard=get_admin_help_inline_keyboard())
            return True

        # /admins
        if text.lower() in ("/admins",):
            logger.info("ADMIN_CMD /admins user_id=%d peer_id=%s", from_id, peer_id)
            log_admin_action(from_id, "/admins", peer_id)
            admins = get_admins()
            if not admins:
                self.bot.send_message(
                    peer_id,
                    "👑 Список администраторов пуст.",
                    keyboard=get_main_menu_keyboard(),
                )
                return True

            admin_list = ""
            try:
                users_info = self.bot.vk_api.users.get(
                    user_ids=sorted(admins),
                    fields="",
                )
                admin_list = "\n".join(
                    f"• [id{u['id']}|{u['first_name']} {u['last_name']}]"
                    for u in users_info
                )
            except ApiError as e:
                logger.error("Ошибка получения информации об админах: %s", e)
                admin_list = "\n".join(f"• {aid}" for aid in sorted(admins))
            except Exception as e:
                logger.error("Ошибка получения информации об админах: %s", e)
                admin_list = "\n".join(f"• {aid}" for aid in sorted(admins))

            self.bot.send_message(
                peer_id,
                f"👑 Список администраторов ({len(admins)} шт.):\n\n{admin_list}",
                keyboard=get_main_menu_keyboard(),
            )
            return True

        # /stats
        if text.lower() == "/stats":
            logger.info("ADMIN_CMD /stats user_id=%d peer_id=%s", from_id, peer_id)
            log_admin_action(from_id, "/stats", peer_id)
            stats = get_stats()
            self.bot.send_message(
                peer_id,
                STATS_RESPONSE.format(
                    total_messages=stats["total_messages"],
                    llm_messages=stats["llm_messages"],
                    errors=stats["errors"],
                ),
                keyboard=get_main_menu_keyboard(),
            )
            return True

        # /stop
        if text.lower() == "/stop":
            logger.info("ADMIN_CMD /stop user_id=%d peer_id=%s", from_id, peer_id)
            log_admin_action(from_id, "/stop", peer_id)
            self.bot.send_message(peer_id, "🛑 Останавливаю бота...")
            if self._shutdown_event is not None:
                self._shutdown_event.set()
            else:
                sys.exit(0)
            return True

        # /restart
        if text.lower() == "/restart":
            logger.info("ADMIN_CMD /restart user_id=%d peer_id=%s", from_id, peer_id)
            log_admin_action(from_id, "/restart", peer_id)
            self.bot.send_message(peer_id, "🔄 Перезагружаю бота...")
            self.bot.request_restart()
            if self._shutdown_event is not None:
                self._shutdown_event.set()
            else:
                python = sys.executable
                os.execl(python, python, *sys.argv)
            return True

        # /delete_db
        if text.lower() == "/delete_db":
            logger.info("ADMIN_CMD /delete_db user_id=%d peer_id=%s", from_id, peer_id)
            log_admin_action(from_id, "/delete_db", peer_id)
            close_all_connections()
            logger.info("Все соединения с БД закрыты перед удалением файлов.")
            time.sleep(3)

            base = Path(settings.db_file).resolve()
            backup_path = base.with_suffix(".db.backup")
            try:
                if base.exists():
                    shutil.copy2(base, backup_path)
                    logger.info("Создан бэкап БД: %s", backup_path)
            except Exception as e:
                logger.error("Не удалось создать бэкап БД: %s", e)

            targets = [
                base,
                base.with_name(base.name + "-wal"),
                base.with_name(base.name + "-shm"),
            ]
            removed = []
            errors = []

            for path in targets:
                for attempt in range(5):
                    try:
                        if path.exists():
                            logger.info("Удаляю файл БД: %s (попытка %d/5)", path, attempt + 1)
                            path.unlink()
                            removed.append(str(path))
                            logger.info("Удалён файл БД: %s", path)
                        else:
                            logger.debug("Файл БД не найден, пропускаю: %s", path)
                        break
                    except PermissionError as e:
                        if attempt < 4:
                            logger.warning("Файл %s заблокирован (попытка %d/5), жду 2 сек...", path, attempt + 1)
                            time.sleep(2)
                        else:
                            errors.append(f"{path}: {e}")
                            logger.error("Не удалось удалить файл БД %s: %s", path, e)
                    except Exception as e:
                        errors.append(f"{path}: {e}")
                        logger.error("Не удалось удалить файл БД %s: %s", path, e)
                        break

            logger.info("Удаление завершено: удалено=%d, ошибок=%d", len(removed), len(errors))
            if errors:
                self.bot.send_message(
                    peer_id,
                    "❌ Ошибки при удалении БД:\n" + "\n".join(errors) + "\n\nОстановите бота и удалите файлы вручную.",
                    keyboard=get_main_menu_keyboard(),
                )
            else:
                self.bot.send_message(
                    peer_id,
                    f"🗑️ Файлы БД удалены: {len(removed)} шт.\n" + "\n".join(removed) + "\n\nПерезагружаю бота...",
                    keyboard=get_main_menu_keyboard(),
                )
                self.bot.request_restart()
                if self._shutdown_event is not None:
                    self._shutdown_event.set()
                else:
                    python = sys.executable
                    os.execl(python, python, *sys.argv)
            return True

        # /admin_add
        if text.lower().startswith("/admin_add"):
            logger.info("ADMIN_CMD /admin_add user_id=%d peer_id=%s text=%s", from_id, peer_id, text)
            log_admin_action(from_id, "/admin_add", peer_id)
            parts = text.strip().split()
            if len(parts) != 2:
                self.bot.send_message(
                    peer_id,
                    "Использование: /admin_add <user_id>\nПример: /admin_add 123456789",
                    keyboard=get_main_menu_keyboard(),
                )
                return True
            try:
                new_id = int(parts[1])
            except (ValueError, OverflowError):
                self.bot.send_message(
                    peer_id,
                    "Некорректный user_id: ожидается целое положительное число.\nПример: /admin_add 123456789",
                    keyboard=get_main_menu_keyboard(),
                )
                return True
            if not (1 <= new_id <= 9_999_999_999):
                self.bot.send_message(
                    peer_id,
                    "Некорректный user_id: значение вне допустимого диапазона (1..9999999999).",
                    keyboard=get_main_menu_keyboard(),
                )
                return True
            if add_admin(new_id):
                self.bot.send_message(
                    peer_id,
                    f"✅ Администратор добавлен: user_id={new_id}",
                    keyboard=get_main_menu_keyboard(),
                )
                try:
                    notify_admins(
                        self.bot.vk_api,
                        [new_id],
                        "✅ Вам выданы права администратора.",
                    )
                except Exception as e:
                    logger.error("Не удалось уведомить нового админа %d: %s", new_id, e)
                    self.bot.send_message(
                        peer_id,
                        f"✅ Администратор добавлен: user_id={new_id}\n⚠️ Не удалось отправить уведомление: {e}",
                        keyboard=get_main_menu_keyboard(),
                    )
            else:
                self.bot.send_message(
                    peer_id,
                    f"ℹ️ user_id={new_id} уже является администратором.",
                    keyboard=get_main_menu_keyboard(),
                )
            return True

        # /admin_del
        if text.lower().startswith("/admin_del"):
            logger.info("ADMIN_CMD /admin_del user_id=%d peer_id=%s text=%s", from_id, peer_id, text)
            log_admin_action(from_id, "/admin_del", peer_id)
            parts = text.strip().split()
            if len(parts) != 2:
                self.bot.send_message(
                    peer_id,
                    "Использование: /admin_del <user_id>\nПример: /admin_del 123456789",
                    keyboard=get_main_menu_keyboard(),
                )
                return True
            try:
                target_id = int(parts[1])
            except (ValueError, OverflowError):
                self.bot.send_message(
                    peer_id,
                    "Некорректный user_id: ожидается целое положительное число.\nПример: /admin_del 123456789",
                    keyboard=get_main_menu_keyboard(),
                )
                return True
            if not (1 <= target_id <= 9_999_999_999):
                self.bot.send_message(
                    peer_id,
                    "Некорректный user_id: значение вне допустимого диапазона (1..9999999999).",
                    keyboard=get_main_menu_keyboard(),
                )
                return True
            if remove_admin(target_id):
                self.bot.send_message(
                    peer_id,
                    f"🗑️ Администратор удалён: user_id={target_id}",
                    keyboard=get_main_menu_keyboard(),
                )
                try:
                    notify_admins(
                        self.bot.vk_api,
                        [target_id],
                        "ℹ️ Ваши права администратора были отозваны.",
                    )
                except Exception as e:
                    logger.error("Не удалось уведомить удалённого админа %d: %s", target_id, e)
                    self.bot.send_message(
                        peer_id,
                        f"🗑️ Администратор удалён: user_id={target_id}\n⚠️ Не удалось отправить уведомление: {e}",
                        keyboard=get_main_menu_keyboard(),
                    )
            else:
                self.bot.send_message(
                    peer_id,
                    f"ℹ️ user_id={target_id} не является администратором.",
                    keyboard=get_main_menu_keyboard(),
                )
            return True

        return False


class MessageRouter:
    """Маршрутизатор текстовых сообщений: фильтры, LLM, простые ответы."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    def route(self, from_id: int, peer_id: int, text: str, event: Any) -> bool:
        """Возвращает True, если сообщение обработано."""
        # Антиспам
        if is_spam_banned(from_id):
            return True

        if not check_ratelimit(
            from_id,
            max_msgs=settings.rate_limit_count,
            window_minutes=settings.rate_limit_minutes,
        ):
            self.bot.send_message(peer_id, RATE_LIMIT_RESPONSE)
            return True

        is_spam, _ = analyze_message_for_spam(text)
        if is_spam:
            ban_for_spam(from_id, minutes=settings.spam_ban_minutes)
            self.bot.send_message(
                peer_id,
                SPAM_RESPONSE,
                keyboard=get_main_menu_keyboard(),
            )
            return True

        handled = handle_message(self.bot, event)

        if not handled:
            self.bot.send_message(
                peer_id,
                NOT_UNDERSTOOD_RESPONSE.format(text=text),
                keyboard=get_main_menu_keyboard(),
            )
        return True


class Server:
    """VK Long Poll сервер: фасад, объединяющий компоненты."""

    def __init__(
        self,
        api_token: str,
        group_id: int,
        server_name: str = "Empty",
        shutdown_event: Optional[threading.Event] = None,
    ) -> None:
        self.server_name = server_name
        self.api_token = api_token
        self.group_id = group_id
        self.vk = vk_api.VkApi(token=api_token)
        self.long_poll = VkBotLongPoll(self.vk, group_id, wait=60)
        self.vk_api = self.vk.get_api()
        self._shutdown_event = shutdown_event
        self._restart_requested = False

        self.chat_client = None
        try:
            from .services.gigachat_client import get_client
            self.chat_client = get_client(max_retries=0)
        except Exception as e:
            logger.error("Не удалось инициализировать GigaChat-клиент: %s", e)

        self.peer_ids = load_peer_ids()
        self.admin_handler = AdminCommandHandler(self, shutdown_event)
        self.message_router = MessageRouter(self)

        logger.info(
            "Сервер «%s» инициализирован. Пользователей в базе: %d",
            self.server_name,
            len(self.peer_ids),
        )

    @property
    def shutdown_event(self) -> Optional[threading.Event]:
        return self._shutdown_event

    def request_restart(self) -> None:
        self._restart_requested = True

    def _reconnect(self) -> None:
        """Пересоздаёт VK API и Long Poll после разрыва соединения."""
        logger.info("Пересоздаю соединение с VK API...")
        self.vk = vk_api.VkApi(token=self.api_token)
        self.long_poll = VkBotLongPoll(self.vk, self.group_id)
        self.vk_api = self.vk.get_api()
        logger.info("Соединение восстановлено.")

    def get_peer_ids(self) -> set[int]:
        """Возвращает копию set ID пользователей (для планировщика)."""
        return set(self.peer_ids)

    def send_message(self, peer_id: int | None, message: str, keyboard: str | None = None) -> None:
        if not peer_id:
            return
        try:
            params = {
                "peer_id": peer_id,
                "message": message,
                "random_id": get_random_id(),
            }
            if keyboard is not None:
                params["keyboard"] = keyboard
            self.vk_api.messages.send(**params)
        except ApiError as e:
            if e.code == VK_ERROR_USER_BLOCKED:
                logger.info(
                    "Отправка peer_id=%s: пользователь не принимает сообщения от группы",
                    peer_id,
                )
                mark_user_blocked(peer_id, reason=f"VK {VK_ERROR_USER_BLOCKED}: blocked")
            else:
                logger.error(
                    "VK API ошибка отправки peer_id=%s: [код %s] %s",
                    peer_id, e.code, e,
                )
        except Exception as e:
            logger.error("Ошибка отправки сообщения peer_id=%s: %s", peer_id, e)

    def start(self) -> None:
        from .scheduler.runner import start_scheduler
        start_scheduler(
            vk_api_instance=self.vk_api,
            peer_ids_func=self.get_peer_ids,
            delay_seconds=SCHEDULER_DELAY_SECONDS,
            chat_client=self.chat_client,
            admin_ids=get_admins(),
            health_interval_minutes=SCHEDULER_HEALTH_INTERVAL_MINUTES,
        )

        logger.info("Сервер «%s» запущен, слушаю события...", self.server_name)

        while True:
            if self._shutdown_event is not None and self._shutdown_event.is_set():
                logger.info("Получен сигнал завершения, останавливаюсь...")
                break
            try:
                for event in self.long_poll.listen():
                    if self._shutdown_event is not None and self._shutdown_event.is_set():
                        logger.info("Получен сигнал завершения во время Long Poll, останавливаюсь...")
                        break
                    try:
                        self._process_event(event)
                    except KeyboardInterrupt:
                        raise
                    except Exception:
                        logger.exception(
                            "Неперехваченное исключение при обработке события, "
                            "продолжаю работу"
                        )
                        increment_stats(errors=1)
                if self._shutdown_event is not None and self._shutdown_event.is_set():
                    break
            except KeyboardInterrupt:
                logger.info("Получен KeyboardInterrupt, останавливаюсь...")
                break
            except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout, TimeoutError, ConnectionError, ConnectionResetError) as e:
                logger.warning(
                    "Соединение разорвано: %s. Переподключение через 5 сек...", e
                )
                time.sleep(5)
                try:
                    self._reconnect()
                except Exception as reconnect_err:
                    logger.error("Не удалось переподключиться: %s", reconnect_err)
            except ApiError as e:
                logger.error(
                    "Ошибка VK API: %s. Переподключение через 10 сек...", e
                )
                time.sleep(10)
                try:
                    self._reconnect()
                except Exception as reconnect_err:
                    logger.error("Не удалось переподключиться: %s", reconnect_err)
            except Exception as e:
                logger.error(
                    "Непредвиденная ошибка в цикле Long Poll: %s. "
                    "Переподключение через 15 сек...",
                    e,
                    exc_info=True,
                )
                time.sleep(15)
                try:
                    self._reconnect()
                except Exception as reconnect_err:
                    logger.error("Не удалось переподключиться: %s", reconnect_err)

    def _process_event(self, event: Any) -> None:
        """Обработка одного события Long Poll."""

        # --- Inline-кнопки (MESSAGE_EVENT) ---
        if event.type == VkBotEventType.MESSAGE_EVENT:
            try:
                handle_callback(self, event)
            except Exception:
                logger.exception("Ошибка при обработке callback-события")
            return

        # --- Текстовые сообщения (MESSAGE_NEW) ---
        if event.type != VkBotEventType.MESSAGE_NEW:
            return

        from_id = event.message.from_id
        peer_id = event.message.peer_id
        text = event.message.text or ""

        if not from_id or from_id <= 0:
            return

        self.peer_ids = add_peer_id(self.peer_ids, from_id)
        increment_stats(total=1)

        # --- Запрос прав администратора от пользователя ---
        if self._handle_admin_request(from_id, peer_id, text):
            return

        # --- Админ-команды ---
        if self.admin_handler.handle(from_id, peer_id, text):
            return

        # --- Маршрутизация пользовательских сообщений ---
        self.message_router.route(from_id, peer_id, text, event)

    def _handle_admin_request(self, from_id: int, peer_id: int, text: str) -> bool:
        """Обрабатывает запрос прав администратора. Возвращает True, если обработано."""
        admin_request_phrases = ("права администратора", "права администраторв")
        if from_id in get_admins() or text.lower() not in admin_request_phrases:
            return False

        logger.info(
            "ADMIN_REQUEST user_id=%d peer_id=%s text=%s",
            from_id, peer_id, text,
        )
        admins = get_admins()
        if not admins:
            self.send_message(
                peer_id,
                "Сейчас нет администраторов, которые могут обработать твой запрос.",
                keyboard=get_main_menu_keyboard(),
            )
            return True

        for admin_id in admins:
            try:
                notify_admins(
                    self.vk_api,
                    [admin_id],
                    (
                        "🔔 Запрос прав администратора\n\n"
                        f"От: [id{from_id}|user_id={from_id}]\n"
                        f"Текст: «{text}»\n\n"
                        "Чтобы добавить: /admin_add " + str(from_id)
                    ),
                )
            except Exception as e:
                logger.error(
                    "Не удалось отправить уведомление админу %d: %s", admin_id, e
                )

        self.send_message(
            peer_id,
            "✅ Запрос прав администратора отправлен. Ожидайте ответа.",
            keyboard=get_main_menu_keyboard(),
        )
        return True


__all__ = ["Server", "Bot", "AdminCommandHandler", "MessageRouter"]
