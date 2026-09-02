from __future__ import annotations

from collections.abc import Iterable

from app.models.common import MetricName, Role, SYSTEM_AVAILABILITY_METRIC, TargetType
from app.models.config import TargetDefinition, UserDefinition, UserSubscription
from app.models.telemetry import MetricSnapshot, TargetSnapshot
from app.utils.time import format_datetime


METRIC_LABELS: dict[MetricName, tuple[str, str]] = {
    MetricName.CPU: ("CPU", "⚙️"),
    MetricName.RAM: ("RAM", "🧠"),
    MetricName.DISK: ("Диск", "💽"),
    MetricName.TEMPERATURE: ("Температура", "🌡"),
}

TARGET_TYPE_LABELS: dict[TargetType, str] = {
    TargetType.PHYSICAL: "physical",
    TargetType.BLADE: "блейд",
    TargetType.VM: "виртуальная машина",
    TargetType.CONTAINER: "контейнер",
}

ROLE_LABELS: dict[Role, str] = {
    Role.ADMIN: "admin",
    Role.USER: "user",
}


def humanize_metric_value(snapshot: MetricSnapshot) -> str:
    if not snapshot.available or snapshot.value is None:
        if snapshot.error:
            return f"недоступно ({snapshot.error})"
        return "данные недоступны"
    suffix = "%" if snapshot.unit == "percent" else "°C" if snapshot.unit == "celsius" else snapshot.unit
    return f"{snapshot.value:.1f} {suffix}".strip()


def format_target_summary(snapshot: TargetSnapshot, timezone_name: str) -> str:
    availability = "🟢 доступен" if snapshot.available else "🔴 недоступен"
    if snapshot.available is None:
        availability = "🟡 состояние неизвестно"
    lines = [
        f"🖥 <b>{snapshot.target.name}</b>",
        f"🏷 Тип: <code>{TARGET_TYPE_LABELS[snapshot.target.type]}</code>",
        f"ℹ️ {snapshot.target.description}",
        f"📡 Статус: {availability}",
    ]
    for metric_name in [MetricName.CPU, MetricName.RAM, MetricName.DISK, MetricName.TEMPERATURE]:
        metric = snapshot.metrics.get(metric_name)
        if metric is None:
            continue
        label, emoji = METRIC_LABELS[metric_name]
        lines.append(f"{emoji} {label}: {humanize_metric_value(metric)}")
    lines.append(f"🕒 Обновлено: {format_datetime(snapshot.collected_at, timezone_name)}")
    if snapshot.error:
        lines.append(f"⚠️ {snapshot.error}")
    return "\n".join(lines)


def format_target_list(targets: Iterable[TargetDefinition]) -> str:
    lines = ["📋 <b>Доступные таргеты</b>"]
    for target in targets:
        lines.append(
            f"• <b>{target.name}</b> (<code>{target.id}</code>) - {TARGET_TYPE_LABELS[target.type]}, "
            f"{'включен' if target.enabled else 'выключен'}\n  {target.description}"
        )
    return "\n".join(lines)


def format_metric_catalog() -> str:
    return (
        "📈 <b>Поддерживаемые метрики</b>\n"
        "• CPU - загрузка CPU в процентах.\n"
        "• RAM - использование оперативной памяти в процентах.\n"
        "• Диск - использование корневой файловой системы в процентах.\n"
        "• Температура - максимальная температура по node_exporter hwmon, доступна только для physical/blade.\n"
        "Для контейнеров CPU, RAM и диск берутся из cAdvisor."
    )


def format_user_subscriptions(
    user_subscription: UserSubscription | None,
    targets_by_id: dict[str, TargetDefinition],
) -> str:
    if user_subscription is None or not user_subscription.targets:
        return "📭 У вас пока нет активных подписок."

    lines = ["🔔 <b>Ваши подписки</b>"]
    for item in user_subscription.targets:
        target = targets_by_id.get(item.target_id)
        title = target.name if target else item.target_id
        metrics = ", ".join(metric.value for metric in item.metrics)
        lines.append(f"• <b>{title}</b> (<code>{item.target_id}</code>) - {metrics}")
    return "\n".join(lines)


def format_users(users: Iterable[UserDefinition], title: str) -> str:
    lines = [title]
    for user in users:
        username = f"@{user.username}" if user.username else "без username"
        lines.append(
            f"• user_id=<code>{user.user_id}</code>, chat_id=<code>{user.chat_id}</code>, "
            f"{username}, role=<code>{ROLE_LABELS[user.role]}</code>, "
            f"{'enabled' if user.enabled else 'disabled'}"
        )
    return "\n".join(lines)


def format_health_report(
    *,
    bot_ok: bool,
    prometheus_ok: bool,
    config_summary: str,
    users_count: int,
    targets_count: int,
    subscriptions_count: int,
) -> str:
    return "\n".join(
        [
            "❤️ <b>Состояние бота</b>",
            f"🤖 Бот: {'ok' if bot_ok else 'degraded'}",
            f"📡 Prometheus: {'ok' if prometheus_ok else 'unreachable'}",
            f"⚙️ Конфиги: {config_summary}",
            f"👥 Пользователи: {users_count}",
            f"🖥 Таргеты: {targets_count}",
            f"🔔 Подписок: {subscriptions_count}",
        ]
    )


def format_alert_message(
    *,
    target_name: str,
    target_type: str,
    metric_name: str,
    current_value: str,
    threshold: str,
    repeated: bool,
) -> str:
    prefix = "🚨 Повторная тревога" if repeated else "🚨 Тревога"
    return "\n".join(
        [
            f"{prefix}",
            f"Таргет: <b>{target_name}</b>",
            f"Тип: <code>{target_type}</code>",
            f"Метрика: <code>{metric_name}</code>",
            f"Текущее значение: <b>{current_value}</b>",
            f"Порог: <b>{threshold}</b>",
        ]
    )


def format_recovery_message(
    *,
    target_name: str,
    target_type: str,
    metric_name: str,
    current_value: str,
) -> str:
    pretty_metric = "availability" if metric_name == SYSTEM_AVAILABILITY_METRIC else metric_name
    return "\n".join(
        [
            "✅ Восстановление",
            f"Таргет: <b>{target_name}</b>",
            f"Тип: <code>{target_type}</code>",
            f"Метрика: <code>{pretty_metric}</code>",
            f"Текущее значение: <b>{current_value}</b>",
        ]
    )
