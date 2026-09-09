# VK Bot: бот для ВКонтакте с GigaChat

**Версия:** `0.0.1`

Умный бот для сообщества ВКонтакте: рассылка, проверка доступности GigaChat, антиспам, ведение истории диалогов и еженедельная очистка старых сообщений.

## 📋 Возможности

- **Интеграция с GigaChat**: генерация ответов, проверка статуса (health‑check), уведомления админов при сбоях.
- **Рассылка сообщений**: автоматическая по расписанию + ручная, с учётом игнор‑листа и лимитов VK API.
- **Антиспам и фильтрация**: проверка на запрещённый контент, ограничение частоты сообщений, бан за спам.
- **История диалогов**: сохранение переписки, статистика, еженедельная очистка по лимиту записей.
- **Админ‑панель**: команды `/health`, уведомления, управление состоянием.
- **Планировщик задач**: фоновый поток с расписанием (рассылка, health‑check, очистка истории).

## 🗂 Структура проекта

```text
vk_bot/
├── .env                    # Переменные окружения (токены, флаги)
├── .gitignore              # Игнорируемые файлы
├── main.py                 # Точка входа
├── requirements.txt        # Зависимости (runtime + dev)
├── admins.yaml             # Файл с администраторами
│
└── src/
    ├── __init__.py         # Публичный интерфейс пакета src
    ├── config.py           # Чтение и валидация .env (VK_API_TOKEN, GIGACHAT_AUTH_KEY и др.)
    ├── prompts.py          # Промпты, заглушки, параметры моделей (включая MODEL)
    ├── chat.py             # Логика запросов к GigaChat, обработка ошибок
    ├── server.py           # Long Poll, маршрутизация, антиспам, админ‑команды
    │
    ├── db/                 # Работа с SQLite
    │   ├── __init__.py      # Реэкспорт функций БД
    │   ├── connection.py    # Thread-local SQLite, retry_on_lock, close_all_connections
    │   ├── schema.py        # Создание таблиц и индексов (init_db)
    │   ├── users.py         # load_peer_ids, add_peer_id, mark_user_blocked, get_blocked_ids
    │   ├── chat_history.py  # save_message, load_history, clear_chat_history, prune_all_history
    │   ├── stats.py         # increment_stats, get_stats
    │   └── spam.py          # check_ratelimit, is_spam_banned, ban_for_spam, analyze_message_for_spam
    │
    ├── filters/            # Фильтры контента и нормализация текста
    │   ├── __init__.py      # Экспорт is_adult_content, ADULT_KEYWORDS, ADULT_RESPONSES, normalize_text
    │   ├── adult.py         # is_adult_content, списки слов и ответов
    │   ├── spam.py          # Реэкспорт analyze_message_for_spam из db/spam.py
    │   └── utils.py         # normalize_text
    │
    ├── keyboards/           # Клавиатуры VK
    │   ├── __init__.py      # Экспорт get_main_menu_keyboard, get_inline_keyboard
    │   ├── main_menu.py     # get_main_menu_keyboard
    │   ├── inline.py        # get_inline_keyboard
    │   └── types.py         # Цвета кнопок (COLOR_ACTION, COLOR_INFO, COLOR_DANGER, COLOR_DEFAULT)
    │
    ├── handlers/           # Обработчики событий
    │   ├── __init__.py      # Экспорт handle_message, handle_callback, normalize_text_for_triggers
    │   ├── message.py       # Обработка входящих сообщений (команды, триггеры, 18+, LLM)
    │   ├── callback.py      # Обработка callback-событий (inline-кнопки)
    │   └── utils.py         # normalize_text_for_triggers
    │
    ├── services/           # Бизнес-сервисы
    │   ├── __init__.py      # Экспорт broadcast_hello, run_health_check, check_gigachat_manual
    │   ├── broadcaster.py   # Рассылка с retry при rate limit и ведением игнор-листа
    │   ├── health.py        # Health-check GigaChat (авто/ручной), уведомления админов
    │   └── gigachat_client.py # get_client — клиент GigaChat с retry-параметрами
    │
    └── scheduler/          # Планировщик задач
        ├── __init__.py      # from .runner import start_scheduler
        ├── constants.py     # BROADCAST_MESSAGE, интервалы, PRUNE_TIME, PRUNE_KEEP_RECORDS
        ├── jobs.py          # job_broadcast, job_health, job_prune
        └── runner.py        # start_scheduler — запуск фонового потока с задачами
│
└── logs/                   # Логи (создаются автоматически при старте)
    ├── bot.info.log        # Информационные логи
    └── bot.error.log       # Логи ошибок
```

## 🚀 Быстрый старт

**Требуется Python >= 3.10**

### 1. Подготовка окружения

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 3. Настройка .env

Создай файл `.env` в корне проекта и добавь:

```dotenv
VK_API_TOKEN=ваш_токен_сообщества
VK_GROUP_ID=id_группы
GIGACHAT_AUTH_KEY=Bearer ваш_ключ_GigaChat
LOG_DIR=logs
DB_FILE=vk_bot.db
ADMIN_IDS=000000000,000000000
SERVER_NAME=MyVKBot
```

### 4. Инициализация БД и запуск

```bash
python main.py
```

При первом запуске автоматически:

- создаётся папка `logs/` и файлы логов;
- создаётся и инициализируется база данных `vk_bot.db`;
- запускается Long Poll и планировщик задач.

## ⚙️ Конфигурация и параметры

| Переменная | Назначение | Пример значения |
| --- | --- | --- |
| `VK_API_TOKEN` | Токен сообщества VK | `v123456...` |
| `VK_GROUP_ID` | ID группы (число) | `123456789` |
| `GIGACHAT_AUTH_KEY` | Ключ для GigaChat (с префиксом `Bearer`) | `Bearer xxxxx...` |
| `LOG_DIR` | Папка для логов | `logs` |
| `DB_FILE` | Путь к файлу SQLite | `vk_bot.db` |
| `ADMIN_IDS` | Список ID администраторов (через запятую) | `123456,789012` |
| `SERVER_NAME` | Имя сервера в логах | `MyVKBot` |

## 🤖 Команды для администратора

- `/health` — ручная проверка доступности GigaChat и вывод статуса.
- `/stats` — статистика бота.
- `/admins` — список администраторов.
- `/admin_add <id>` — добавить администратора.
- `/admin_del <id>` — удалить администратора.
- `/delete_db` — удалить базу данных.
- `/stop` — остановить бота.
- `/restart` — перезагрузить бота.
- `/help` — справка.

При изменении статуса бот автоматически уведомляет всех админов из `ADMIN_IDS`.

## 📅 Расписание задач (планировщик)

Планировщик запускается автоматически при старте бота:

- **Рассылка** — каждые 24 часа.
- **Health‑check GigaChat** — каждые 10 минут (настраивается через `health_interval_minutes`).
- **Очистка истории** — каждый понедельник в `03:00` (оставляет последние 500 записей на пользователя).

## 🎨 Клавиатуры и цвета кнопок

В проекте используются стандартные цвета VK:

- `COLOR_ACTION` → `VkKeyboardColor.POSITIVE` (яркое действие)
- `COLOR_INFO` → `VkKeyboardColor.SECONDARY` (вспомогательная информация)
- `COLOR_DANGER` → `VkKeyboardColor.NEGATIVE` (опасное/важное действие)
- `COLOR_DEFAULT` → `VkKeyboardColor.PRIMARY` (нейтральный цвет по умолчанию)

Примечание: `VkKeyboardColor.DEFAULT` не существует в `vk_api`, поэтому используется `PRIMARY`.

## 🧪 Тестирование и разработка

Для локальной разработки доступны инструменты:

```bash
pytest
black . --check
flake8 src/
mypy src/
```

## 📚 Зависимости

**Runtime:**

- `vk-api` — работа с API ВКонтакте.
- `gigachat` — клиент для GigaChat.
- `pytz` — работа с часовыми поясами.
- `schedule` — планировщик задач.
- `python-dotenv` — загрузка переменных из `.env`.

**Dev:**

- `pytest`, `black`, `flake8`, `mypy` — тестирование, форматирование, линтинг, статическая типизация.

## 🧩 Использование

1. Добавьте группу в сообщество ВКонтакте как администратора.
2. Включите Long Poll API в настройках группы.
3. Запустите бота командой `python main.py`.
4. Для управления используйте команды администратора или клавиатуру бота.

## ⚠️ Troubleshooting

- **Ошибка `RuntimeError: VK_API_TOKEN не найден в .env`** — проверьте, что файл `.env` лежит в корне проекта и содержит `VK_API_TOKEN`.
- **Ошибка `RuntimeError: VK_GROUP_ID не задан или некорректен`** — проверьте, что в `.env` указан `VK_GROUP_ID` (число, положительное).
- **Ошибка `vk_api.exceptions.ApiError: [901]`** — пользователь запретил сообщения от сообщества. Бот автоматически пометит его в БД и не будет отправлять ему сообщения.
- **Ошибка `sqlite3.OperationalError: database is locked`** — при интенсивной записи может сработать блокировка. Бот автоматически повторяет запрос до 3 раз. Если ошибка persists — проверьте, что нет параллельных процессов, работающих с той же БД.
- **Ошибка импорта `ModuleNotFoundError`** — убедитесь, что активировано виртуальное окружение и установлены зависимости: `pip install -r requirements.txt`.
- **Бот не отвечает** — проверьте логи в папке `logs/`, убедитесь, что Long Poll запущен и токен группы действителен.

## 🤝 Contributing

1. Создайте форк репозитория.
2. Создайте ветку с названием фичи: `git checkout -b feature/имя-фичи`.
3. Внесите изменения и убедитесь, что код проходит проверки:
   ```bash
   black . --check
   flake8 src/
   mypy src/
   pytest
   ```
4. Отправьте пул-реквест с описанием изменений.

## 📝 Лицензия

Проект распространяется под лицензией MIT (если не указано иное).
