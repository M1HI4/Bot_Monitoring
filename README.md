# Monitoring Bot

Telegram-бот для подписок на метрики Prometheus. Prometheus, node_exporter и cAdvisor должны быть уже развернуты на сервере или доступны боту по сети.

## Что мониторится

- Блейды: `type: "blade"`, метрики node_exporter: CPU, RAM, disk, temperature.
- Виртуальные машины: `type: "vm"`, метрики node_exporter: CPU, RAM, disk.
- Docker-контейнеры: `type: "container"`, метрики cAdvisor: CPU, RAM, disk.

В меню подписки таргеты сгруппированы по категориям: блейды, виртуальные машины и контейнеры.

## Что изменить перед запуском

1. Создайте `.env` из `.env.example` и задайте:
   - `TELEGRAM_BOT_TOKEN` - токен Telegram-бота.
   - `PROMETHEUS_BASE_URL` - URL Prometheus HTTP API, например `http://prometheus.internal:9090`.
2. В `configs/users.yaml` укажите реальные `user_id`, `chat_id`, `username` и `role`.
3. В `configs/targets.yaml` замените примеры на реальные targets из Prometheus:
   - для блейдов и виртуальных машин используйте labels node_exporter, обычно `job` и `instance`;
   - для контейнеров используйте labels cAdvisor, например `job`, `instance`, `name` или другие labels, которые есть в вашем Prometheus.
4. В `configs/alerts.yaml` при необходимости измените пороги для `blade`, `vm` и `container`.

## Пример контейнера cAdvisor

```yaml
- id: "docker-container-01"
  name: "Docker Container 01"
  type: "container"
  description: "Docker container from cAdvisor."
  prometheus:
    job: "cadvisor"
    instance: "192.0.2.40:8080"
    name: "example-container"
  enabled: true
```

Labels в блоке `prometheus` должны совпадать с labels cAdvisor в Prometheus. Проверить их можно запросами в Prometheus UI, например `container_last_seen` или `container_cpu_usage_seconds_total`.

## Запуск на сервере через Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f monitoring-bot
```

`docker-compose.yml` запускает только Telegram-бота. Prometheus, node_exporter и cAdvisor в этот compose не входят.

## Запуск без Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

## Администрирование

- Пользователи задаются в `configs/users.yaml`.
- При удалении пользователя через кнопки бот показывает `user_id`, `username` и роль, чтобы было понятно, кого удаляем.
- Конфиги можно перечитать из админ-меню или командой `/reload`.
