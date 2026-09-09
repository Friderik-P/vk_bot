# vk_bot/src/server.py
"""VK Long Poll сервер: маршрутизация сообщений, антиспам, админ-команды."""

import logging
import os
import sys
import time
from pathlib import Path

import requests
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
from vk_api.exceptions import ApiError

from .config import DB_FILE, RATE_LIMIT_COUNT, RATE_LIMIT_MINUTES, SPAM_BAN_MINUTES
from .db import (
    load_peer_ids,
    add_peer_id,
    mark_user_blocked,
    check_ratelimit,
    is_spam_banned,
    ban_for_spam,
    get_stats,
    increment_stats,
)
from .db.connection import close_all_connections
from .filters.spam import analyze_message_for_spam
from .keyboards.main_menu import get_main_menu_keyboard
from .keyboards.inline import get_admin_help_inline_keyboard
from .services.health import check_gigachat_manual
from .admins import get_admins, add_admin, remove_admin

logger = logging.getLogger(__name__)


class Server:
    def __init__(self, api_token, group_id, server_name="Empty"):
        self.server_name = server_name
        self.api_token = api_token
        self.group_id = group_id
        self.vk = vk_api.VkApi(token=api_token)
        self.long_poll = VkBotLongPoll(self.vk, group_id, wait=60)
        self.vk_api = self.vk.get_api()

        # Инициализируем GigaChat-клиент (для health-check: max_retries=0)
        self.chat_client = None
        try:
            from .services.gigachat_client import get_client
            self.chat_client = get_client(max_retries=0)
        except Exception as e:
            logger.error("Не удалось инициализировать GigaChat-клиент: %s", e)

        # Загружаем пользователей (init_db уже вызван в main.py)
        self.peer_ids = load_peer_ids()
        logger.info(
            "Сервер «%s» инициализирован. Пользователей в базе: %d",
            self.server_name,
            len(self.peer_ids),
        )

    def _reconnect(self):
        """Пересоздаёт VK API и Long Poll после разрыва соединения."""
        logger.info("Пересоздаю соединение с VK API...")
        self.vk = vk_api.VkApi(token=self.api_token)
        self.long_poll = VkBotLongPoll(self.vk, self.group_id)
        self.vk_api = self.vk.get_api()
        logger.info("Соединение восстановлено.")

    def get_peer_ids(self):
        """Возвращает копию set ID пользователей (для планировщика)."""
        return set(self.peer_ids)

    def send_message(self, peer_id, message, keyboard=None):
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
            if e.code == 901:
                logger.info(
                    "Отправка peer_id=%s: пользователь не принимает сообщения от группы",
                    peer_id,
                )
                mark_user_blocked(peer_id, reason="VK 901: blocked")
            else:
                logger.error(
                    "VK API ошибка отправки peer_id=%s: [код %s] %s",
                    peer_id, e.code, e,
                )
        except Exception as e:
            logger.error("Ошибка отправки сообщения peer_id=%s: %s", peer_id, e)

    def start(self):
        from .scheduler.runner import start_scheduler
        start_scheduler(
            vk_api_instance=self.vk_api,
            peer_ids_func=self.get_peer_ids,
            delay_seconds=0.2,
            chat_client=self.chat_client,
            admin_ids=get_admins(),
            health_interval_minutes=10,
        )

        from .handlers import handle_message, handle_callback

        logger.info("Сервер «%s» запущен, слушаю события...", self.server_name)

        while True:
            try:
                for event in self.long_poll.listen():
                    try:
                        self._process_event(event, handle_message, handle_callback)
                    except KeyboardInterrupt:
                        raise
                    except Exception:
                        logger.exception(
                            "Неперехваченное исключение при обработке события, "
                            "продолжаю работу"
                        )
                        increment_stats(errors=1)
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

    def _process_event(self, event, handle_message, handle_callback):
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
        admin_request_phrases = ("права администратора", "права администраторв")
        if from_id not in get_admins() and text.lower() in admin_request_phrases:
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
                return
            for admin_id in admins:
                try:
                    self.vk_api.messages.send(
                        peer_id=admin_id,
                        message=(
                            "🔔 Запрос прав администратора\n\n"
                            f"От: [id{from_id}|user_id={from_id}]\n"
                            f"Текст: «{text}»\n\n"
                            "Чтобы добавить: /admin_add " + str(from_id)
                        ),
                        random_id=get_random_id(),
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
            return

        # --- Команды администратора ---
        if from_id in get_admins() and text.lower().startswith("/health"):
            logger.info("ADMIN_CMD /health user_id=%d peer_id=%s", from_id, peer_id)
            if self.chat_client is None:
                self.send_message(peer_id, "❌ GigaChat-клиент не инициализирован.")
            else:
                report = check_gigachat_manual(self.chat_client)
                self.send_message(peer_id, report)
            return

        if from_id in get_admins() and text.lower() in ("/help", "помощь"):
            logger.info("ADMIN_CMD /help user_id=%d peer_id=%s", from_id, peer_id)
            self.send_message(
                peer_id,
                "Я умею:\n"
                "🐱 Мяукать\n"
                "💬 Болтать на любые темы\n"
                "🔄 /reset — сбросить диалог\n"
                "ℹ️ Контакты — связь со мной\n\n"
                "Просто напиши мне что угодно!",
                keyboard=get_main_menu_keyboard(),
            )
            admin_help = (
                "👑 Админ-команды:\n"
                "/health — проверка GigaChat\n"
                "/stats — статистика\n"
                "/admins — список администраторов\n"
                "/admin_add <id> — добавить администратора\n"
                "/admin_del <id> — удалить администратора\n"
                "/delete_db — удалить базу данных\n"
                "/stop — остановить бота\n"
                "/restart — перезагрузить бота"
            )
            self.send_message(peer_id, admin_help, keyboard=get_admin_help_inline_keyboard())
            return

        if from_id in get_admins() and text.lower() in ("/admins",):
            logger.info("ADMIN_CMD /admins user_id=%d peer_id=%s", from_id, peer_id)
            admins = get_admins()
            admin_list = "\n".join(f"• {aid}" for aid in sorted(admins))
            self.send_message(
                peer_id,
                f"👑 Список администраторов ({len(admins)} шт.):\n\n{admin_list}",
                keyboard=get_main_menu_keyboard(),
            )
            return

        if from_id in get_admins() and text.lower() == "/stats":
            logger.info("ADMIN_CMD /stats user_id=%d peer_id=%s", from_id, peer_id)
            stats = get_stats()
            report = (
                "📊 Статистика бота\n\n"
                f"💬 Всего сообщений: {stats['total_messages']}\n"
                f"🤖 Через LLM (GigaChat): {stats['llm_messages']}\n"
                f"⚠️ Ошибок: {stats['errors']}\n\n"
                "Мяу! Всё под контролем. 🐱"
            )
            self.send_message(peer_id, report, keyboard=get_main_menu_keyboard())
            return

        if from_id in get_admins() and text.lower() == "/stop":
            logger.info("ADMIN_CMD /stop user_id=%d peer_id=%s", from_id, peer_id)
            self.send_message(peer_id, "🛑 Останавливаю бота...")
            sys.exit(0)

        if from_id in get_admins() and text.lower() == "/restart":
            logger.info("ADMIN_CMD /restart user_id=%d peer_id=%s", from_id, peer_id)
            self.send_message(peer_id, "🔄 Перезагружаю бота...")
            python = sys.executable
            os.execl(python, python, *sys.argv)

        if from_id in get_admins() and text.lower() == "/delete_db":
            logger.info("ADMIN_CMD /delete_db user_id=%d peer_id=%s", from_id, peer_id)
            close_all_connections()
            logger.info("Все соединения с БД закрыты перед удалением файлов.")
            time.sleep(3)

            base = Path(DB_FILE).resolve()
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
                self.send_message(
                    peer_id,
                    "❌ Ошибки при удалении БД:\n" + "\n".join(errors) + "\n\nОстановите бота и удалите файлы вручную.",
                    keyboard=get_main_menu_keyboard(),
                )
            else:
                self.send_message(
                    peer_id,
                    f"🗑️ Файлы БД удалены: {len(removed)} шт.\n" + "\n".join(removed) + "\n\nПерезагружаю бота...",
                    keyboard=get_main_menu_keyboard(),
                )
                time.sleep(1)
                python = sys.executable
                os.execl(python, python, *sys.argv)
            return

        if from_id in get_admins() and text.lower().startswith("/admin_add"):
            logger.info("ADMIN_CMD /admin_add user_id=%d peer_id=%s text=%s", from_id, peer_id, text)
            parts = text.strip().split()
            if len(parts) != 2 or not parts[1].lstrip("-").isdigit():
                self.send_message(
                    peer_id,
                    "Использование: /admin_add <user_id>\nПример: /admin_add 123456789",
                    keyboard=get_main_menu_keyboard(),
                )
                return
            new_id = int(parts[1])
            if add_admin(new_id):
                self.send_message(
                    peer_id,
                    f"✅ Администратор добавлен: user_id={new_id}",
                    keyboard=get_main_menu_keyboard(),
                )
                try:
                    self.vk_api.messages.send(
                        peer_id=new_id,
                        message="✅ Вам выданы права администратора.",
                        random_id=get_random_id(),
                    )
                except ApiError as e:
                    if e.code == 901:
                        logger.info(
                            "Не удалось уведомить нового админа %d: пользователь не принимает сообщения от группы",
                            new_id,
                        )
                        self.send_message(
                            peer_id,
                            f"✅ Администратор добавлен: user_id={new_id}\n⚠️ Не удалось отправить уведомление: пользователь не принимает сообщения от группы.",
                            keyboard=get_main_menu_keyboard(),
                        )
                    else:
                        raise
                except Exception as e:
                    logger.error("Не удалось уведомить нового админа %d: %s", new_id, e)
                    self.send_message(
                        peer_id,
                        f"✅ Администратор добавлен: user_id={new_id}\n⚠️ Не удалось отправить уведомление: {e}",
                        keyboard=get_main_menu_keyboard(),
                    )
            else:
                self.send_message(
                    peer_id,
                    f"ℹ️ user_id={new_id} уже является администратором.",
                    keyboard=get_main_menu_keyboard(),
                )
            return

        if from_id in get_admins() and text.lower().startswith("/admin_del"):
            logger.info("ADMIN_CMD /admin_del user_id=%d peer_id=%s text=%s", from_id, peer_id, text)
            parts = text.strip().split()
            if len(parts) != 2 or not parts[1].lstrip("-").isdigit():
                self.send_message(
                    peer_id,
                    "Использование: /admin_del <user_id>\nПример: /admin_del 123456789",
                    keyboard=get_main_menu_keyboard(),
                )
                return
            target_id = int(parts[1])
            if remove_admin(target_id):
                self.send_message(
                    peer_id,
                    f"🗑️ Администратор удалён: user_id={target_id}",
                    keyboard=get_main_menu_keyboard(),
                )
                try:
                    self.vk_api.messages.send(
                        peer_id=target_id,
                        message="ℹ️ Ваши права администратора были отозваны.",
                        random_id=get_random_id(),
                    )
                except ApiError as e:
                    if e.code == 901:
                        logger.info(
                            "Не удалось уведомить удалённого админа %d: пользователь не принимает сообщения от группы",
                            target_id,
                        )
                        self.send_message(
                            peer_id,
                            f"🗑️ Администратор удалён: user_id={target_id}\n⚠️ Не удалось отправить уведомление: пользователь не принимает сообщения от группы.",
                            keyboard=get_main_menu_keyboard(),
                        )
                    else:
                        raise
                except Exception as e:
                    logger.error("Не удалось уведомить удалённого админа %d: %s", target_id, e)
                    self.send_message(
                        peer_id,
                        f"🗑️ Администратор удалён: user_id={target_id}\n⚠️ Не удалось отправить уведомление: {e}",
                        keyboard=get_main_menu_keyboard(),
                    )
            else:
                self.send_message(
                    peer_id,
                    f"ℹ️ user_id={target_id} не является администратором.",
                    keyboard=get_main_menu_keyboard(),
                )
            return

        # --- Антиспам ---
        if is_spam_banned(from_id):
            return

        if not check_ratelimit(
            from_id,
            max_msgs=RATE_LIMIT_COUNT,
            window_minutes=RATE_LIMIT_MINUTES,
        ):
            self.send_message(peer_id, "Слишком много сообщений 🐱")
            return

        is_spam, _ = analyze_message_for_spam(text)
        if is_spam:
            ban_for_spam(from_id, minutes=SPAM_BAN_MINUTES)
            self.send_message(
                peer_id,
                "Мяу... не пиши капсом и не спамь эмодзи. Я пока промолчу 🐱",
                keyboard=get_main_menu_keyboard(),
            )
            return

        handled = handle_message(self, event)

        if not handled:
            self.send_message(
                peer_id,
                f"Я не понял: «{text}». Попробуй кнопку «Мяу» или «Помощь».",
                keyboard=get_main_menu_keyboard(),
            )
