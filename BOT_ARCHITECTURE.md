# Monitoring Bot: структура, назначение файлов и поток данных

Этот документ объединяет:

1. Структуру директории `monitoring-bot`
2. Объяснение, за что отвечает каждый файл
3. Удобное описание того, как данные текут по проекту
4. Итоговые текстовые схемы для основных сценариев

## Структура директории

Ниже показана структура полезных исходников и конфигов в `monitoring-bot`.
Каталоги `__pycache__` здесь не указаны, потому что это автоматически сгенерированный Python-кэш, а не логика бота.

```text
monitoring-bot/
├─ .dockerignore
├─ .env
├─ .env.example
├─ docker-compose.yml
├─ Dockerfile
├─ README.md
├─ requirements.txt
├─ configs/
│  ├─ alerts.yaml
│  ├─ config.yaml
│  ├─ subscriptions.yaml
│  ├─ targets.yaml
│  └─ users.yaml
├─ runtime/
│  └─ alert_state.yaml
└─ app/
   ├─ __init__.py
   ├─ container.py
   ├─ main.py
   ├─ bot/
   │  ├─ __init__.py
   │  ├─ callbacks.py
   │  ├─ dispatcher.py
   │  ├─ handlers/
   │  │  ├─ __init__.py
   │  │  ├─ admin.py
   │  │  ├─ common.py
   │  │  ├─ helpers.py
   │  │  ├─ subscriptions.py
   │  │  └─ summaries.py
   │  ├─ keyboards/
   │  │  ├─ __init__.py
   │  │  ├─ common.py
   │  │  └─ menus.py
   │  ├─ middlewares/
   │  │  ├─ __init__.py
   │  │  ├─ access.py
   │  │  └─ chat_guard.py
   │  └─ states/
   │     ├─ __init__.py
   │     ├─ admin.py
   │     └─ subscription.py
   ├─ models/
   │  ├─ __init__.py
   │  ├─ common.py
   │  ├─ config.py
   │  └─ telemetry.py
   ├─ services/
   │  ├─ __init__.py
   │  ├─ alerts/
   │  │  ├─ __init__.py
   │  │  └─ service.py
   │  ├─ config/
   │  │  ├─ __init__.py
   │  │  └─ service.py
   │  ├─ prometheus/
   │  │  ├─ __init__.py
   │  │  ├─ client.py
   │  │  ├─ queries.py
   │  │  └─ service.py
   │  ├─ subscriptions/
   │  │  ├─ __init__.py
   │  │  └─ service.py
   │  └─ users/
   │     ├─ __init__.py
   │     └─ service.py
   ├─ storage/
   │  ├─ __init__.py
   │  └─ yaml_storage.py
   └─ utils/
      ├─ __init__.py
      ├─ exceptions.py
      ├─ formatting.py
      ├─ logging.py
      └─ time.py
```

## За что отвечает каждый файл

### Корень проекта

- `.dockerignore`
  - Исключает `__pycache__`, `*.pyc`, локальный `.env` и `.venv` из Docker-контекста сборки.

- `.env`
  - Основной файл переменных окружения для запуска.
  - Хранит `TELEGRAM_BOT_TOKEN` и `PROMETHEUS_BASE_URL`.
  - Используется `Docker Compose`, а также загружается из `app/main.py`.

- `.env.example`
  - Шаблон для `.env`.
  - Показывает, какие переменные нужно обязательно заполнить.

- `docker-compose.yml`
  - Запускает бота как один контейнер.
  - Собирает образ по `Dockerfile`.
  - Загружает переменные из `.env`.
  - Монтирует `configs` и `runtime` внутрь контейнера.

- `Dockerfile`
  - Собирает Docker-образ бота.
  - Использует `python:3.12-slim`.
  - Устанавливает зависимости из `requirements.txt`.
  - Копирует `app`, `configs` и `runtime`.
  - Запускает бота через `python -m app.main`.

- `README.md`
  - Короткая инструкция по эксплуатации.
  - Объясняет, что нужно изменить перед запуском и как запускать бота.

- `requirements.txt`
  - Список Python-зависимостей:
  - `aiogram` для Telegram-бота
  - `httpx` для Prometheus HTTP API
  - `PyYAML` для YAML-конфигов
  - `pydantic` для валидации конфигов
  - `python-dotenv` для загрузки `.env`

### Конфиги

- `configs/config.yaml`
  - Главный конфиг приложения.
  - Определяет источник токена Telegram, URL Prometheus, поведение приложения, уровень логирования, интервал фоновой проверки алертов, временную зону и пути до остальных YAML-файлов.

- `configs/users.yaml`
  - Whitelist пользователей Telegram.
  - Хранит `user_id`, `chat_id`, `username`, `role` и `enabled`.
  - Используется для проверки доступа к боту.

- `configs/targets.yaml`
  - Список таргетов мониторинга.
  - Для каждого таргета содержит `id`, `name`, `type`, `description`, `prometheus` labels и `enabled`.
  - Используется для связи логического сервера с реальными labels в Prometheus.

- `configs/alerts.yaml`
  - Настройки алертов и порогов.
  - Содержит общий интервал повторов, настройки алертов доступности и пороги для `cpu`, `ram`, `disk` и `temperature`.

- `configs/subscriptions.yaml`
  - Хранилище пользовательских подписок.
  - Содержит, кто на какой таргет и какие метрики подписан.

### Runtime

- `runtime/alert_state.yaml`
  - Хранит текущее состояние алертов.
  - Используется, чтобы помнить активные тревоги, повторные отправки, время восстановления и последнее отправленное сообщение.
  - Нужен для дедупликации и защиты от спама.

### app/

- `app/__init__.py`
  - Помечает `app` как Python-пакет.

- `app/main.py`
  - Основная точка входа.
  - Загружает `.env`, настраивает логирование, собирает сервисы, создает Telegram-бота, запускает polling и фоновый alert worker.
  - Также корректно закрывает HTTP-сессии при остановке.

- `app/container.py`
  - Собирает все сервисы приложения.
  - Создает объект `AppServices`, в котором находятся сервисы конфигов, пользователей, подписок, Prometheus, мониторинга, состояния алертов и фонового алертинга.

### app/bot/

- `app/bot/__init__.py`
  - Помечает пакет Telegram-бота.

- `app/bot/callbacks.py`
  - Определяет структуры callback payload для inline-кнопок.
  - Содержит схемы callback-данных для главного меню, подписок, сводок и админских действий.

- `app/bot/dispatcher.py`
  - Создает aiogram `Dispatcher`.
  - Подключает FSM memory storage.
  - Регистрирует middlewares.
  - Подключает все routers: common, subscriptions, summaries, admin.

### app/bot/handlers/

- `app/bot/handlers/__init__.py`
  - Помечает пакет handlers.

- `app/bot/handlers/helpers.py`
  - Общие вспомогательные функции для handlers.
  - Умеет либо отправить новое сообщение, либо отредактировать старое callback-сообщение.

- `app/bot/handlers/common.py`
  - Базовые команды и общий пользовательский интерфейс.
  - Обрабатывает `/start`, `/help`, `/targets`, `/metrics`, `/health`, `/status`, `/reload`, `/admin`.
  - Также обрабатывает навигацию по главному меню и глобальные ошибки.

- `app/bot/handlers/subscriptions.py`
  - Полный сценарий подписок.
  - Обрабатывает `/subscribe`, `/subscriptions`, `/unsubscribe`.
  - Поддерживает выбор таргетов, выбор метрик, редактирование подписок и удаление подписок.
  - Использует FSM-состояния для пошагового сценария.

- `app/bot/handlers/summaries.py`
  - Сценарий сводок.
  - Обрабатывает `/summary`.
  - Может показать сводку по одному таргету или по всем таргетам, на которые подписан пользователь.

- `app/bot/handlers/admin.py`
  - Админские сценарии и команды.
  - Обрабатывает `/admin_add_user`, `/admin_remove_user`, `/admin_set_role`.
  - Поддерживает inline-админку, список пользователей, whitelist, смену ролей, удаление пользователей, reload конфигов и проверку Prometheus.

### app/bot/keyboards/

- `app/bot/keyboards/__init__.py`
  - Помечает пакет клавиатур.

- `app/bot/keyboards/common.py`
  - Общие небольшие кнопки: Назад, Домой, Обновить.

- `app/bot/keyboards/menus.py`
  - Строит все inline-меню:
  - главное меню
  - меню выбора таргетов
  - меню выбора метрик
  - меню подписок
  - меню управления подпиской
  - меню сводок
  - админ-панель
  - список пользователей для админских действий и меню выбора роли

### app/bot/middlewares/

- `app/bot/middlewares/__init__.py`
  - Помечает пакет middlewares.

- `app/bot/middlewares/chat_guard.py`
  - Проверяет, что бот используется только в личных чатах.
  - Блокирует сообщения из групп и каналов.

- `app/bot/middlewares/access.py`
  - Проверяет, есть ли пользователь в whitelist.
  - Если доступ разрешен, кладет `current_user` в контекст handler.

### app/bot/states/

- `app/bot/states/__init__.py`
  - Помечает пакет состояний.

- `app/bot/states/subscription.py`
  - FSM-состояния для сценария подписки.
  - Содержит состояния выбора таргетов, выбора метрик и редактирования метрик.

- `app/bot/states/admin.py`
  - FSM-состояние для сценария добавления пользователя админом.

### app/models/

- `app/models/__init__.py`
  - Помечает пакет моделей.

- `app/models/common.py`
  - Общие enum-ы и константы.
  - Определяет роли, типы таргетов, имена метрик, severity алертов и системную метрику `availability`.

- `app/models/config.py`
  - Pydantic-схемы для всех конфигов и runtime-данных.
  - Валидирует:
  - runtime config
  - targets
  - users
  - alerts
  - subscriptions
  - alert state

- `app/models/telemetry.py`
  - Dataclass-модели собранной телеметрии.
  - `MetricSnapshot` представляет результат одной метрики.
  - `TargetSnapshot` представляет полную сводку по таргету: доступность, метрики и ошибки.

### app/services/

- `app/services/__init__.py`
  - Помечает пакет сервисов.

### app/services/config/

- `app/services/config/__init__.py`
  - Помечает пакет сервисов конфигурации.

- `app/services/config/service.py`
  - Загружает YAML-файлы и валидирует их через Pydantic-модели.
  - Подставляет `${ENV_VAR}` из окружения.
  - Создает недостающие runtime-файлы при необходимости.
  - Сохраняет пользователей, подписки и состояние алертов обратно на диск.

### app/services/prometheus/

- `app/services/prometheus/__init__.py`
  - Помечает пакет сервисов Prometheus.

- `app/services/prometheus/client.py`
  - Низкоуровневый асинхронный HTTP-клиент для Prometheus.
  - Отправляет запросы в `/api/v1/query`.
  - Проверяет health Prometheus через `/-/healthy`.
  - Преобразует HTTP-ошибки и timeout в исключения приложения.

- `app/services/prometheus/queries.py`
  - Строит PromQL-запросы.
  - Содержит определения метрик для CPU, RAM, Disk, Temperature и Availability.
  - Знает, какие метрики поддерживаются для каких типов таргетов.

- `app/services/prometheus/service.py`
  - Высокоуровневая логика мониторинга.
  - Загружает включенные таргеты.
  - Строит снапшоты по одному или нескольким таргетам.
  - Проверяет, что выбранные метрики допустимы для типа таргета.
  - Работает через `PrometheusClient`.

### app/services/users/

- `app/services/users/__init__.py`
  - Помечает пакет сервисов пользователей.

- `app/services/users/service.py`
  - Логика работы с пользователями.
  - Читает whitelist, проверяет роли, ищет пользователей по `user_id + chat_id`, добавляет пользователей, удаляет пользователей и меняет роли.

### app/services/subscriptions/

- `app/services/subscriptions/__init__.py`
  - Помечает пакет сервисов подписок.

- `app/services/subscriptions/service.py`
  - Логика работы с подписками.
  - Читает подписки пользователя, обновляет метрики по таргету, сохраняет несколько подписок сразу, удаляет подписки и очищает все подписки пользователя.

### app/services/alerts/

- `app/services/alerts/__init__.py`
  - Помечает пакет сервисов алертов.

- `app/services/alerts/service.py`
  - Движок фоновых алертов.
  - `AlertStateService` работает с `runtime/alert_state.yaml`.
  - `AlertingService` запускает цикл, проверяет таргеты и подписанные метрики, сравнивает их с порогами, отправляет alert/recovery-сообщения и обновляет runtime-состояние алертов.

### app/storage/

- `app/storage/__init__.py`
  - Помечает пакет storage.

- `app/storage/yaml_storage.py`
  - Низкоуровневая работа с YAML-файлами.
  - Читает YAML.
  - Записывает YAML атомарно через временный файл и `os.replace`.
  - Создает недостающие YAML-файлы.
  - Использует блокировки, чтобы уменьшить риск гонок записи.

### app/utils/

- `app/utils/__init__.py`
  - Помечает пакет утилит.

- `app/utils/exceptions.py`
  - Исключения приложения:
  - отказ в доступе
  - невалидная конфигурация
  - ошибка запроса к Prometheus
  - недоступная метрика

- `app/utils/formatting.py`
  - Преобразует сырые данные в понятные Telegram-сообщения.
  - Форматирует список таргетов, список метрик, подписки, health-report, сводку по таргету, alert-сообщение и recovery-сообщение.

- `app/utils/logging.py`
  - Настраивает Python logging: уровень логов и формат строки.

- `app/utils/time.py`
  - Утилиты для работы со временем.
  - Возвращает текущее UTC-время.
  - Переводит время в ISO8601.
  - Парсит ISO8601.
  - Форматирует время в заданную временную зону.

### Что можно игнорировать

- `__pycache__` и `.pyc` файлы
  - Это кэш-файлы, а не исходная логика бота.

- `configs/subscriptions.yaml` и `runtime/alert_state.yaml`
  - Это runtime-данные, а не код.
  - Бот сам поддерживает их в актуальном состоянии во время работы.

## Как данные текут по проекту

В проекте есть два основных потока данных:

1. Интерактивный поток
   - Пользователь отправляет команду или нажимает кнопку
   - Бот проверяет доступ
   - Бот загружает конфиги и при необходимости читает подписки
   - Бот может запросить данные у Prometheus
   - Бот форматирует ответ
   - Бот отправляет его обратно в Telegram

2. Фоновый поток
   - Периодический воркер просыпается
   - Бот читает таргеты, пользователей, подписки и пороги алертов
   - Бот запрашивает текущие метрики у Prometheus
   - Бот сравнивает их с порогами
   - Бот отправляет alert или recovery-сообщения
   - Бот сохраняет состояние алертов

### 1. Запуск бота

Поток запуска:

`.env` -> загрузка конфигов -> создание сервисов -> создание Telegram-бота -> запуск polling -> запуск фонового alert worker

Основные файлы:

- `app/main.py`
  - Загружает `.env`
  - Настраивает логирование
  - Собирает сервисы
  - Создает `Bot`
  - Запускает polling
  - Запускает фонового воркера алертов

- `app/container.py`
  - Создает все сервисы и возвращает `AppServices`

- `app/services/config/service.py`
  - Загружает YAML-конфиги и подставляет значения из переменных окружения

- `configs/config.yaml`
  - Определяет, где лежат данные и как работает приложение

- `.env`
  - Передает токен Telegram и URL Prometheus

### 2. Поток входящего Telegram-сообщения

Поток интерактивного запроса:

`Telegram -> aiogram polling -> Dispatcher -> Middlewares -> Handler -> Services -> Formatter -> Telegram reply`

Основные файлы:

- `app/bot/dispatcher.py`
  - Центральная точка маршрутизации

- `app/bot/middlewares/chat_guard.py`
  - Отклоняет запросы не из личных чатов

- `app/bot/middlewares/access.py`
  - Проверяет пользователя по whitelist

- `app/services/users/service.py`
  - Ищет пользователя в `configs/users.yaml`

Если пользователь не допущен:
- запрос останавливается сразу
- бот отправляет сообщение об отказе в доступе

Если пользователь допущен:
- middleware кладет `current_user` в контекст
- запрос передается в нужный handler

### 3. Как определяется нужный сценарий

После middlewares обновление попадает в handlers:

- `app/bot/handlers/common.py`
  - базовые команды и главное меню

- `app/bot/handlers/subscriptions.py`
  - управление подписками

- `app/bot/handlers/summaries.py`
  - сводки

- `app/bot/handlers/admin.py`
  - админские действия

Для текстовых команд:
- aiogram матчится по `Command(...)`

Для нажатий на кнопки:
- callback payload разбираются через:
  - `MenuCallback`
  - `SubscriptionCallback`
  - `SummaryCallback`
  - `AdminCallback`

Эти callback-классы описаны в `app/bot/callbacks.py`.

### 4. Откуда бот берет данные

Основные источники данных для бота:

1. YAML-файлы
2. Prometheus HTTP API

Используемые YAML-файлы:

- `configs/config.yaml`
- `configs/users.yaml`
- `configs/targets.yaml`
- `configs/alerts.yaml`
- `configs/subscriptions.yaml`
- `runtime/alert_state.yaml`

Путь чтения YAML:

`Handler -> ConfigService -> YamlStorage -> YAML file`

Основные файлы:

- `app/services/config/service.py`
  - Загружает и валидирует YAML

- `app/storage/yaml_storage.py`
  - Физически читает и пишет файлы

- `app/models/config.py`
  - Дает строгие схемы данных

Путь работы с Prometheus:

`Handler или AlertingService -> MonitoringService -> PrometheusClient -> Prometheus HTTP API`

Основные файлы:

- `app/services/prometheus/service.py`
- `app/services/prometheus/client.py`
- `app/services/prometheus/queries.py`

### 5. Как работает запрос сводки

Поток сводки:

`User -> summaries handler -> subscriptions service -> monitoring service -> Prometheus client -> formatter -> Telegram reply`

По шагам:

1. Пользователь отправляет `/summary` или нажимает кнопку сводки
2. `app/bot/handlers/summaries.py` определяет, какие таргеты и метрики доступны пользователю по подпискам
3. `app/services/subscriptions/service.py` читает `configs/subscriptions.yaml`
4. `app/services/prometheus/service.py` строит снапшоты таргетов
5. `app/services/prometheus/queries.py` генерирует PromQL
6. `app/services/prometheus/client.py` отправляет запросы в `/api/v1/query`
7. Результаты преобразуются в `MetricSnapshot` и `TargetSnapshot`
8. `app/utils/formatting.py` превращает их в понятный текст для Telegram
9. Handler отправляет итоговое сообщение

Если кратко:

- `configs/subscriptions.yaml` говорит, что пользователю разрешено смотреть
- `configs/targets.yaml` говорит, как найти таргет в Prometheus
- `queries.py` говорит, каким PromQL это спрашивать
- `formatting.py` говорит, как это красиво показать

### 6. Как работает сценарий подписки

Поток подписки:

`User -> FSM state -> target selection -> metric selection -> save to subscriptions.yaml`

Основные файлы:

- `app/bot/handlers/subscriptions.py`
- `app/bot/states/subscription.py`
- `app/bot/keyboards/menus.py`
- `app/services/subscriptions/service.py`

По шагам:

1. Пользователь отправляет `/subscribe`
2. FSM переходит в состояние выбора таргетов
3. Бот показывает включенные таргеты из `configs/targets.yaml`
4. Пользователь выбирает один или несколько таргетов
5. Бот показывает поддерживаемые метрики для каждого таргета
6. Для `vm` метрика `temperature` исключается по правилам поддержки метрик
7. После сохранения результат записывается в `configs/subscriptions.yaml`

`configs/subscriptions.yaml` становится картой:
- какой пользователь подписан
- на какой таргет
- с каким набором метрик

### 7. Как работает фоновый alerting

Фоновый поток:

`Timer -> read subscriptions -> read targets -> query Prometheus -> compare with thresholds -> send alerts/recoveries -> update alert_state.yaml`

Основные файлы:

- `app/main.py`
  - запускает фонового воркера

- `app/services/alerts/service.py`
  - запускает цикл алертов

- `configs/alerts.yaml`
  - содержит пороги и интервалы повторов

- `configs/subscriptions.yaml`
  - определяет, что именно проверять для каждого пользователя

- `runtime/alert_state.yaml`
  - хранит память о состоянии алертов

По шагам:

1. `AlertingService` просыпается
2. Читает текущий интервал фоновой проверки из `configs/config.yaml`
3. Загружает включенные таргеты, пользователей, подписки и конфиг алертов
4. Строит снапшоты из Prometheus
5. Проверяет доступность таргета через `up`
6. Проверяет подписанные метрики относительно порогов
7. Смотрит в `runtime/alert_state.yaml`, активен ли уже такой алерт и когда он в последний раз отправлялся
8. При необходимости отправляет новый или повторный alert
9. При восстановлении отправляет recovery-сообщение
10. Сохраняет обновленное состояние обратно в `runtime/alert_state.yaml`

Именно это защищает от спама:
- бот помнит активные алерты
- и повторяет их только по заданному интервалу

### 8. Как готовится текст для Telegram

Поток форматирования:

`Сырые данные -> formatting helpers -> готовый HTML-текст для Telegram`

Основной файл:

- `app/utils/formatting.py`

Он отвечает за:
- список таргетов
- каталог метрик
- пользовательские подписки
- health-report
- сводку по таргету
- alert-сообщение
- recovery-сообщение

Handlers в основном не строят длинный текст вручную.
Они собирают данные и передают их в formatting helpers.

### 9. Удобное разделение по слоям

Полезная ментальная модель кодовой базы:

Внешний вход и выход:
- Telegram приходит через `app/bot/dispatcher.py`
- Prometheus вызывается через `app/services/prometheus/client.py`
- YAML-файлы читаются и пишутся через `app/storage/yaml_storage.py`

Бизнес-логика:
- `app/services/users/service.py`
- `app/services/subscriptions/service.py`
- `app/services/prometheus/service.py`
- `app/services/alerts/service.py`
- `app/services/config/service.py`

Слой представления:
- `app/bot/handlers/*.py`
- `app/bot/keyboards/*.py`
- `app/utils/formatting.py`

Модели данных:
- `app/models/common.py`
- `app/models/config.py`
- `app/models/telemetry.py`

### 10. Самая короткая ментальная модель

Если держать проект в голове максимально просто:

- `main.py` запускает все
- `dispatcher.py` принимает события Telegram
- `middlewares` решают, можно ли пускать пользователя дальше
- `handlers` понимают, что именно хочет пользователь
- `services` делают основную работу
- `config/service.py` и `yaml_storage.py` работают с YAML
- `prometheus/client.py` и `prometheus/service.py` работают с Prometheus
- `formatting.py` превращает результаты в читаемые сообщения
- `alerts/service.py` независимо от пользователя следит за порогами и отправляет алерты

## Итоговые текстовые схемы

### A. Общая высокоуровневая схема системы

```text
Пользователь Telegram
   ->
Telegram Bot API
   ->
app/main.py
   ->
app/bot/dispatcher.py
   ->
Middlewares
   - chat_guard.py
   - access.py
   ->
Handlers
   - common.py
   - subscriptions.py
   - summaries.py
   - admin.py
   ->
Services
   - users/service.py
   - subscriptions/service.py
   - config/service.py
   - prometheus/service.py
   - alerts/service.py
   ->
Источники данных
   - configs/*.yaml
   - runtime/alert_state.yaml
   - Prometheus HTTP API
   ->
Форматирование
   - utils/formatting.py
   ->
Ответ в Telegram
```

### B. Схема запроса `/summary`

```text
Пользователь отправляет /summary
   ->
handlers/summaries.py
   ->
subscriptions/service.py читает configs/subscriptions.yaml
   ->
prometheus/service.py выбирает таргет и метрики
   ->
prometheus/queries.py строит PromQL
   ->
prometheus/client.py вызывает Prometheus /api/v1/query
   ->
models/telemetry.py собирает MetricSnapshot / TargetSnapshot
   ->
utils/formatting.py форматирует текст сводки по таргету
   ->
Telegram отправляет сводку обратно пользователю
```

### C. Схема сценария `/subscribe`

```text
Пользователь отправляет /subscribe
   ->
handlers/subscriptions.py
   ->
states/subscription.py переводит сценарий в FSM-состояние
   ->
keyboards/menus.py показывает выбор таргетов
   ->
Пользователь выбирает таргеты
   ->
keyboards/menus.py показывает выбор метрик
   ->
prometheus/service.py проверяет поддержку метрик для типа таргета
   ->
subscriptions/service.py сохраняет выбранный таргет и метрики
   ->
configs/subscriptions.yaml обновляется
   ->
Telegram подтверждает сохранение подписки
```

### D. Схема фонового alerting

```text
app/main.py запускает alert worker
   ->
alerts/service.py входит в цикл
   ->
config/service.py загружает config, users, targets, subscriptions, alerts
   ->
subscriptions/service.py возвращает пользовательские подписки
   ->
prometheus/service.py строит снапшоты таргетов
   ->
prometheus/client.py запрашивает метрики у Prometheus
   ->
alerts/service.py сравнивает значения с порогами из configs/alerts.yaml
   ->
alerts/service.py проверяет runtime/alert_state.yaml
   ->
Если порог превышен:
   -> отправить alert-сообщение в Telegram
   -> обновить runtime/alert_state.yaml
Если метрика восстановилась:
   -> отправить recovery-сообщение в Telegram
   -> обновить runtime/alert_state.yaml
```

### E. Схема контроля доступа

```text
Входящее обновление Telegram
   ->
chat_guard.py
   -> если это не личный чат: отклонить
   ->
access.py
   -> прочитать user_id + chat_id
   -> users/service.py проверяет configs/users.yaml
   -> если пользователя нет в whitelist: отклонить
   ->
Разрешенный запрос попадает в handler с current_user в контексте
```
