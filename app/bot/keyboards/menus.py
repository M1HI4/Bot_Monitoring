from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import AdminCallback, MenuCallback, SubscriptionCallback, SummaryCallback
from app.models.common import MetricName, TargetType
from app.models.config import TargetDefinition, UserDefinition, UserSubscription
from app.services.prometheus.queries import list_supported_metrics

TARGET_CATEGORY_LABELS: dict[TargetType, str] = {
    TargetType.BLADE: "Блейды",
    TargetType.VM: "Виртуальные машины",
    TargetType.CONTAINER: "Контейнеры",
}

TARGET_CATEGORY_ICONS: dict[TargetType, str] = {
    TargetType.BLADE: "🗄",
    TargetType.VM: "💻",
    TargetType.CONTAINER: "📦",
}


def build_main_menu(is_admin: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 Подписаться", callback_data=SubscriptionCallback(action="start").pack())
    builder.button(text="📚 Мои подписки", callback_data=SubscriptionCallback(action="list").pack())
    builder.button(text="📊 Сводка", callback_data=SummaryCallback(action="menu").pack())
    builder.button(text="🖥 Таргеты", callback_data=MenuCallback(page="targets").pack())
    builder.button(text="📈 Метрики", callback_data=MenuCallback(page="metrics").pack())
    builder.button(text="❤️ Проверка", callback_data=MenuCallback(page="health").pack())
    builder.button(text="📡 Статус", callback_data=MenuCallback(page="status").pack())
    builder.button(text="🔄 Обновить", callback_data=MenuCallback(page="reload").pack())
    if is_admin:
        builder.button(text="🛠 Админ-панель", callback_data=AdminCallback(action="menu").pack())
    builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup()


def build_targets_selection_menu(
    selected_target_ids: set[str],
    targets: list[TargetDefinition],
    selected_target_type: TargetType | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=("✅ Все категории" if selected_target_type is None else "Все категории"),
        callback_data=SubscriptionCallback(action="select_category").pack(),
    )
    for target_type, label in TARGET_CATEGORY_LABELS.items():
        marker = "✅" if selected_target_type == target_type else "⬜"
        icon = TARGET_CATEGORY_ICONS[target_type]
        builder.button(
            text=f"{marker} {icon} {label}",
            callback_data=SubscriptionCallback(action="select_category", target_type=target_type.value).pack(),
        )

    visible_targets = [target for target in targets if selected_target_type is None or target.type == selected_target_type]
    for target in visible_targets:
        marker = "✅" if target.id in selected_target_ids else "⬜"
        icon = TARGET_CATEGORY_ICONS.get(target.type, "🖥")
        builder.button(
            text=f"{marker} {icon} {target.name}",
            callback_data=SubscriptionCallback(action="toggle_target", target_id=target.id).pack(),
        )
    builder.button(text="Выбрать все в категории", callback_data=SubscriptionCallback(action="select_all_targets").pack())
    builder.button(text="Далее", callback_data=SubscriptionCallback(action="to_metrics").pack())
    builder.button(text="Назад", callback_data=MenuCallback(page="main").pack())
    builder.button(text="Домой", callback_data=MenuCallback(page="main").pack())
    builder.adjust(1)
    return builder.as_markup()


def build_metrics_selection_menu(
    *,
    target: TargetDefinition,
    selected_metrics: set[MetricName],
    action_prefix: str,
    back_action: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for definition in list_supported_metrics(target.type):
        marker = "✅" if definition.name in selected_metrics else "⬜"
        builder.button(
            text=f"{marker} {definition.display_name}",
            callback_data=SubscriptionCallback(
                action=f"{action_prefix}_toggle_metric",
                target_id=target.id,
                metric=definition.name.value,
            ).pack(),
        )
    builder.button(
        text="Выбрать все метрики",
        callback_data=SubscriptionCallback(action=f"{action_prefix}_select_all_metrics", target_id=target.id).pack(),
    )
    save_action = "save_edit_metrics" if action_prefix == "edit" else "next_target"
    builder.button(
        text="Сохранить",
        callback_data=SubscriptionCallback(action=save_action, target_id=target.id).pack(),
    )
    builder.button(text="Назад", callback_data=SubscriptionCallback(action=back_action, target_id=target.id).pack())
    builder.button(text="Домой", callback_data=MenuCallback(page="main").pack())
    builder.adjust(1)
    return builder.as_markup()


def build_subscriptions_menu(
    user_subscription: UserSubscription | None,
    targets_by_id: dict[str, TargetDefinition],
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if user_subscription:
        for item in user_subscription.targets:
            target = targets_by_id.get(item.target_id)
            title = target.name if target else item.target_id
            builder.button(
                text=f"⚙️ {title}",
                callback_data=SubscriptionCallback(action="manage_target", target_id=item.target_id).pack(),
            )
    builder.button(text="🔔 Добавить подписки", callback_data=SubscriptionCallback(action="start").pack())
    builder.button(text="🔄 Обновить", callback_data=SubscriptionCallback(action="list").pack())
    builder.button(text="Назад", callback_data=MenuCallback(page="main").pack())
    builder.button(text="Домой", callback_data=MenuCallback(page="main").pack())
    builder.adjust(1)
    return builder.as_markup()


def build_manage_subscription_menu(target_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Изменить метрики",
        callback_data=SubscriptionCallback(action="edit_metrics", target_id=target_id).pack(),
    )
    builder.button(
        text="Удалить таргет",
        callback_data=SubscriptionCallback(action="remove_target", target_id=target_id).pack(),
    )
    builder.button(
        text="Сводка по таргету",
        callback_data=SummaryCallback(action="one", target_id=target_id).pack(),
    )
    builder.button(text="Назад", callback_data=SubscriptionCallback(action="list").pack())
    builder.button(text="Домой", callback_data=MenuCallback(page="main").pack())
    builder.adjust(1)
    return builder.as_markup()


def build_summary_menu(user_subscription: UserSubscription | None, targets_by_id: dict[str, TargetDefinition]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if user_subscription and user_subscription.targets:
        builder.button(text="Сводка по всем моим таргетам", callback_data=SummaryCallback(action="all").pack())
        for item in user_subscription.targets:
            target = targets_by_id.get(item.target_id)
            title = target.name if target else item.target_id
            builder.button(
                text=f"📍 {title}",
                callback_data=SummaryCallback(action="one", target_id=item.target_id).pack(),
            )
    builder.button(text="Назад", callback_data=MenuCallback(page="main").pack())
    builder.button(text="Домой", callback_data=MenuCallback(page="main").pack())
    builder.adjust(1)
    return builder.as_markup()


def build_admin_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Все пользователи", callback_data=AdminCallback(action="users").pack())
    builder.button(text="✅ Whitelist", callback_data=AdminCallback(action="whitelist").pack())
    builder.button(text="➕ Добавить пользователя", callback_data=AdminCallback(action="add_prompt").pack())
    builder.button(text="➖ Удалить пользователя", callback_data=AdminCallback(action="remove_menu").pack())
    builder.button(text="🔐 Сменить роль", callback_data=AdminCallback(action="role_menu").pack())
    builder.button(text="🔄 Reload конфигов", callback_data=AdminCallback(action="reload").pack())
    builder.button(text="📡 Статус Prometheus", callback_data=AdminCallback(action="prometheus").pack())
    builder.button(text="❤️ Health бота", callback_data=AdminCallback(action="health").pack())
    builder.button(text="Домой", callback_data=MenuCallback(page="main").pack())
    builder.adjust(1)
    return builder.as_markup()


def build_admin_user_list(users: list[UserDefinition], action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for user in users:
        username = f"@{user.username}" if user.username else "без username"
        caption = f"{username} | id={user.user_id} | {user.role.value}"
        builder.button(text=caption, callback_data=AdminCallback(action=action, user_id=user.user_id).pack())
    builder.button(text="Назад", callback_data=MenuCallback(page="admin").pack())
    builder.button(text="Домой", callback_data=MenuCallback(page="main").pack())
    builder.adjust(1)
    return builder.as_markup()


def build_admin_role_menu(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Сделать admin", callback_data=AdminCallback(action="set_role", user_id=user_id, role="admin").pack())
    builder.button(text="Сделать user", callback_data=AdminCallback(action="set_role", user_id=user_id, role="user").pack())
    builder.button(text="Назад", callback_data=AdminCallback(action="role_menu").pack())
    builder.button(text="Домой", callback_data=MenuCallback(page="main").pack())
    builder.adjust(1)
    return builder.as_markup()
