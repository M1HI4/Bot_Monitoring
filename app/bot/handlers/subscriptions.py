from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.callbacks import SubscriptionCallback
from app.bot.handlers.helpers import answer_or_edit
from app.bot.keyboards.menus import (
    build_main_menu,
    build_manage_subscription_menu,
    build_metrics_selection_menu,
    build_subscriptions_menu,
    build_targets_selection_menu,
)
from app.bot.states.subscription import SubscriptionFlow
from app.container import AppServices
from app.models.common import MetricName, Role, TargetType
from app.models.config import TargetDefinition, UserDefinition
from app.utils.formatting import format_user_subscriptions

router = Router(name="subscriptions")


async def show_subscription_list(
    target: Message | CallbackQuery,
    *,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    targets_by_id = services.monitoring.get_targets_map()
    user_subscription = services.subscriptions.get_user_subscription(current_user.user_id)
    await answer_or_edit(
        target,
        format_user_subscriptions(user_subscription, targets_by_id),
        reply_markup=build_subscriptions_menu(user_subscription, targets_by_id),
    )


async def show_target_selection(
    target: Message | CallbackQuery,
    *,
    services: AppServices,
    state: FSMContext,
) -> None:
    state_data = await state.get_data()
    selected_target_ids = set(state_data.get("selected_target_ids", []))
    selected_target_type_value = state_data.get("selected_target_type")
    selected_target_type = TargetType(selected_target_type_value) if selected_target_type_value else None
    targets = services.monitoring.get_enabled_targets()
    text = (
        "🎯 <b>Выбор таргетов</b>\n"
        "Выберите один или несколько таргетов, затем нажмите «Далее».\n"
        f"Сейчас выбрано: <b>{len(selected_target_ids)}</b>"
    )
    if selected_target_type is not None:
        text += f"\nКатегория: <code>{selected_target_type.value}</code>"

    await answer_or_edit(
        target,
        text,
        reply_markup=build_targets_selection_menu(selected_target_ids, targets, selected_target_type),
    )


async def show_current_metric_selection(
    target: Message | CallbackQuery,
    *,
    services: AppServices,
    state: FSMContext,
    edit_mode: bool,
) -> None:
    state_data = await state.get_data()
    if edit_mode:
        target_id = state_data["editing_target_id"]
    else:
        target_order = state_data["target_order"]
        current_index = int(state_data["current_index"])
        target_id = target_order[current_index]

    target_definition = services.monitoring.get_target_by_id(target_id)
    if target_definition is None:
        await answer_or_edit(target, f"⚠️ Таргет <code>{target_id}</code> больше недоступен.")
        return

    metrics_by_target = state_data.get("metrics_by_target", {})
    supported_metrics = set(services.monitoring.get_supported_metric_names(target_definition.type))
    selected_values = {
        MetricName(metric)
        for metric in metrics_by_target.get(target_id, [])
        if metric in {item.value for item in supported_metrics}
    }
    text = (
        f"📈 <b>Выбор метрик для {target_definition.name}</b>\n"
        f"Тип таргета: <code>{target_definition.type.value}</code>\n"
        "Выберите одну или несколько метрик и сохраните."
    )
    if target_definition.type in {TargetType.VM, TargetType.CONTAINER}:
        text += "\n🌡 Temperature для этого типа таргета недоступна и не показывается."
    if not edit_mode:
        text += f"\nШаг: <b>{int(state_data['current_index']) + 1}</b> из <b>{len(state_data['target_order'])}</b>."
    await answer_or_edit(
        target,
        text,
        reply_markup=build_metrics_selection_menu(
            target=target_definition,
            selected_metrics=selected_values,
            action_prefix="edit" if edit_mode else "create",
            back_action="back_to_manage" if edit_mode else "back_to_targets",
        ),
    )


@router.message(Command("subscribe"))
async def command_subscribe(
    message: Message,
    current_user: UserDefinition,
    services: AppServices,
    state: FSMContext,
) -> None:
    await state.set_state(SubscriptionFlow.selecting_targets)
    await state.set_data({"selected_target_ids": [], "metrics_by_target": {}, "current_index": 0, "target_order": []})
    await show_target_selection(message, services=services, state=state)


@router.message(Command("subscriptions"))
async def command_subscriptions(message: Message, current_user: UserDefinition, services: AppServices) -> None:
    await show_subscription_list(message, current_user=current_user, services=services)


@router.message(Command("unsubscribe"))
async def command_unsubscribe(message: Message, current_user: UserDefinition, services: AppServices) -> None:
    await message.answer("Выберите таргет, который нужно изменить или удалить.")
    await show_subscription_list(message, current_user=current_user, services=services)


@router.callback_query(SubscriptionCallback.filter(F.action == "start"))
async def callback_start_subscribe(
    callback: CallbackQuery,
    current_user: UserDefinition,
    services: AppServices,
    state: FSMContext,
) -> None:
    await state.set_state(SubscriptionFlow.selecting_targets)
    await state.set_data({"selected_target_ids": [], "metrics_by_target": {}, "current_index": 0, "target_order": []})
    await show_target_selection(callback, services=services, state=state)


@router.callback_query(SubscriptionCallback.filter(F.action == "list"))
async def callback_list_subscriptions(
    callback: CallbackQuery,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    await show_subscription_list(callback, current_user=current_user, services=services)


@router.callback_query(StateFilter(SubscriptionFlow.selecting_targets), SubscriptionCallback.filter(F.action == "select_category"))
async def callback_select_category(
    callback: CallbackQuery,
    callback_data: SubscriptionCallback,
    services: AppServices,
    state: FSMContext,
) -> None:
    target_type = callback_data.target_type
    if target_type is not None:
        try:
            TargetType(target_type)
        except ValueError:
            await callback.answer("Категория недоступна.", show_alert=True)
            return
    await state.update_data(selected_target_type=target_type)
    await show_target_selection(callback, services=services, state=state)


@router.callback_query(StateFilter(SubscriptionFlow.selecting_targets), SubscriptionCallback.filter(F.action == "toggle_target"))
async def callback_toggle_target(
    callback: CallbackQuery,
    callback_data: SubscriptionCallback,
    services: AppServices,
    state: FSMContext,
) -> None:
    state_data = await state.get_data()
    selected_target_ids = list(state_data.get("selected_target_ids", []))
    if callback_data.target_id in selected_target_ids:
        selected_target_ids.remove(callback_data.target_id)
    else:
        selected_target_ids.append(callback_data.target_id)
    await state.update_data(selected_target_ids=selected_target_ids)
    await show_target_selection(callback, services=services, state=state)


@router.callback_query(StateFilter(SubscriptionFlow.selecting_targets), SubscriptionCallback.filter(F.action == "select_all_targets"))
async def callback_select_all_targets(
    callback: CallbackQuery,
    services: AppServices,
    state: FSMContext,
) -> None:
    state_data = await state.get_data()
    selected_target_type_value = state_data.get("selected_target_type")
    selected_target_type = TargetType(selected_target_type_value) if selected_target_type_value else None
    selected_target_ids = [
        target.id
        for target in services.monitoring.get_enabled_targets()
        if selected_target_type is None or target.type == selected_target_type
    ]
    await state.update_data(selected_target_ids=selected_target_ids)
    await show_target_selection(callback, services=services, state=state)


@router.callback_query(StateFilter(SubscriptionFlow.selecting_targets), SubscriptionCallback.filter(F.action == "to_metrics"))
async def callback_to_metrics(
    callback: CallbackQuery,
    current_user: UserDefinition,
    services: AppServices,
    state: FSMContext,
) -> None:
    state_data = await state.get_data()
    selected_target_ids = list(state_data.get("selected_target_ids", []))
    if not selected_target_ids:
        await callback.answer("Сначала выберите хотя бы один таргет.", show_alert=True)
        return

    existing_subscription = services.subscriptions.get_user_subscription(current_user.user_id)
    existing_metrics: dict[str, list[str]] = {}
    if existing_subscription:
        for item in existing_subscription.targets:
            target = services.monitoring.get_target_by_id(item.target_id)
            if target is None:
                continue
            allowed = {metric.value for metric in services.monitoring.get_supported_metric_names(target.type)}
            existing_metrics[item.target_id] = [metric.value for metric in item.metrics if metric.value in allowed]

    await state.set_state(SubscriptionFlow.selecting_metrics)
    await state.update_data(
        target_order=selected_target_ids,
        current_index=0,
        metrics_by_target={target_id: existing_metrics.get(target_id, []) for target_id in selected_target_ids},
    )
    await show_current_metric_selection(callback, services=services, state=state, edit_mode=False)


@router.callback_query(StateFilter(SubscriptionFlow.selecting_metrics), SubscriptionCallback.filter(F.action == "create_toggle_metric"))
async def callback_create_toggle_metric(
    callback: CallbackQuery,
    callback_data: SubscriptionCallback,
    services: AppServices,
    state: FSMContext,
) -> None:
    metric = MetricName(callback_data.metric)
    target = services.monitoring.get_target_by_id(callback_data.target_id)
    if target is None:
        await callback.answer("Таргет недоступен.", show_alert=True)
        return
    services.monitoring.validate_metric_selection(target, [metric])

    state_data = await state.get_data()
    metrics_by_target = dict(state_data.get("metrics_by_target", {}))
    current = list(metrics_by_target.get(callback_data.target_id, []))
    if metric.value in current:
        current.remove(metric.value)
    else:
        current.append(metric.value)
    metrics_by_target[callback_data.target_id] = current
    await state.update_data(metrics_by_target=metrics_by_target)
    await show_current_metric_selection(callback, services=services, state=state, edit_mode=False)


@router.callback_query(StateFilter(SubscriptionFlow.selecting_metrics), SubscriptionCallback.filter(F.action == "create_select_all_metrics"))
async def callback_create_select_all_metrics(
    callback: CallbackQuery,
    callback_data: SubscriptionCallback,
    services: AppServices,
    state: FSMContext,
) -> None:
    target = services.monitoring.get_target_by_id(callback_data.target_id)
    if target is None:
        await callback.answer("Таргет недоступен.", show_alert=True)
        return
    metrics = [metric.value for metric in services.monitoring.get_supported_metric_names(target.type)]
    state_data = await state.get_data()
    metrics_by_target = dict(state_data.get("metrics_by_target", {}))
    metrics_by_target[target.id] = metrics
    await state.update_data(metrics_by_target=metrics_by_target)
    await show_current_metric_selection(callback, services=services, state=state, edit_mode=False)


@router.callback_query(StateFilter(SubscriptionFlow.selecting_metrics), SubscriptionCallback.filter(F.action == "next_target"))
async def callback_next_target(
    callback: CallbackQuery,
    current_user: UserDefinition,
    services: AppServices,
    state: FSMContext,
) -> None:
    state_data = await state.get_data()
    target_order = list(state_data["target_order"])
    current_index = int(state_data["current_index"])
    current_target_id = target_order[current_index]
    metrics_by_target = dict(state_data.get("metrics_by_target", {}))
    current_metrics = metrics_by_target.get(current_target_id, [])
    if not current_metrics:
        await callback.answer("Выберите хотя бы одну метрику для текущего таргета.", show_alert=True)
        return

    if current_index + 1 < len(target_order):
        await state.update_data(current_index=current_index + 1)
        await show_current_metric_selection(callback, services=services, state=state, edit_mode=False)
        return

    mapping = {target_id: [MetricName(metric) for metric in metrics] for target_id, metrics in metrics_by_target.items()}
    services.subscriptions.upsert_many(current_user.user_id, mapping)
    await state.clear()
    await answer_or_edit(
        callback,
        "✅ Подписки сохранены.",
        reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN),
    )


@router.callback_query(StateFilter(SubscriptionFlow.selecting_metrics), SubscriptionCallback.filter(F.action == "back_to_targets"))
async def callback_back_to_targets(
    callback: CallbackQuery,
    services: AppServices,
    state: FSMContext,
) -> None:
    await state.set_state(SubscriptionFlow.selecting_targets)
    await show_target_selection(callback, services=services, state=state)


@router.callback_query(SubscriptionCallback.filter(F.action == "manage_target"))
async def callback_manage_target(
    callback: CallbackQuery,
    callback_data: SubscriptionCallback,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    user_subscription = services.subscriptions.get_user_subscription(current_user.user_id)
    target_subscription = None
    if user_subscription:
        target_subscription = next((item for item in user_subscription.targets if item.target_id == callback_data.target_id), None)
    if target_subscription is None:
        await callback.answer("Подписка не найдена.", show_alert=True)
        return
    target = services.monitoring.get_target_by_id(callback_data.target_id)
    target_title = target.name if target else callback_data.target_id
    metrics_text = ", ".join(metric.value for metric in target_subscription.metrics)
    await answer_or_edit(
        callback,
        f"⚙️ <b>{target_title}</b>\nТекущие метрики: <code>{metrics_text}</code>",
        reply_markup=build_manage_subscription_menu(callback_data.target_id),
    )


@router.callback_query(SubscriptionCallback.filter(F.action == "edit_metrics"))
async def callback_edit_metrics(
    callback: CallbackQuery,
    callback_data: SubscriptionCallback,
    current_user: UserDefinition,
    services: AppServices,
    state: FSMContext,
) -> None:
    user_subscription = services.subscriptions.get_user_subscription(current_user.user_id)
    target_subscription = None
    if user_subscription:
        target_subscription = next((item for item in user_subscription.targets if item.target_id == callback_data.target_id), None)
    if target_subscription is None:
        await callback.answer("Подписка не найдена.", show_alert=True)
        return
    target_definition = services.monitoring.get_target_by_id(callback_data.target_id)
    if target_definition is None:
        await callback.answer("Таргет больше недоступен.", show_alert=True)
        return
    allowed_metrics = {item.value for item in services.monitoring.get_supported_metric_names(target_definition.type)}

    await state.set_state(SubscriptionFlow.editing_metrics)
    await state.set_data(
        {
            "editing_target_id": callback_data.target_id,
            "metrics_by_target": {
                callback_data.target_id: [
                    metric.value
                    for metric in target_subscription.metrics
                    if metric.value in allowed_metrics
                ]
            },
        }
    )
    await show_current_metric_selection(callback, services=services, state=state, edit_mode=True)


@router.callback_query(StateFilter(SubscriptionFlow.editing_metrics), SubscriptionCallback.filter(F.action == "edit_toggle_metric"))
async def callback_edit_toggle_metric(
    callback: CallbackQuery,
    callback_data: SubscriptionCallback,
    services: AppServices,
    state: FSMContext,
) -> None:
    metric = MetricName(callback_data.metric)
    target = services.monitoring.get_target_by_id(callback_data.target_id)
    if target is None:
        await callback.answer("Таргет недоступен.", show_alert=True)
        return
    services.monitoring.validate_metric_selection(target, [metric])

    state_data = await state.get_data()
    metrics_by_target = dict(state_data.get("metrics_by_target", {}))
    current = list(metrics_by_target.get(callback_data.target_id, []))
    if metric.value in current:
        current.remove(metric.value)
    else:
        current.append(metric.value)
    metrics_by_target[callback_data.target_id] = current
    await state.update_data(metrics_by_target=metrics_by_target)
    await show_current_metric_selection(callback, services=services, state=state, edit_mode=True)


@router.callback_query(StateFilter(SubscriptionFlow.editing_metrics), SubscriptionCallback.filter(F.action == "edit_select_all_metrics"))
async def callback_edit_select_all_metrics(
    callback: CallbackQuery,
    callback_data: SubscriptionCallback,
    services: AppServices,
    state: FSMContext,
) -> None:
    target = services.monitoring.get_target_by_id(callback_data.target_id)
    if target is None:
        await callback.answer("Таргет недоступен.", show_alert=True)
        return
    metrics = [metric.value for metric in services.monitoring.get_supported_metric_names(target.type)]
    state_data = await state.get_data()
    metrics_by_target = dict(state_data.get("metrics_by_target", {}))
    metrics_by_target[target.id] = metrics
    await state.update_data(metrics_by_target=metrics_by_target)
    await show_current_metric_selection(callback, services=services, state=state, edit_mode=True)


@router.callback_query(StateFilter(SubscriptionFlow.editing_metrics), SubscriptionCallback.filter(F.action == "save_edit_metrics"))
async def callback_save_edit_metrics(
    callback: CallbackQuery,
    current_user: UserDefinition,
    services: AppServices,
    state: FSMContext,
) -> None:
    state_data = await state.get_data()
    target_id = state_data["editing_target_id"]
    metrics_by_target = dict(state_data.get("metrics_by_target", {}))
    metrics = metrics_by_target.get(target_id, [])
    if not metrics:
        await callback.answer("Нужно оставить хотя бы одну метрику. Для удаления используйте кнопку удаления.", show_alert=True)
        return
    services.subscriptions.upsert_target_metrics(
        current_user.user_id,
        target_id,
        [MetricName(metric) for metric in metrics],
    )
    await state.clear()
    await answer_or_edit(
        callback,
        "✅ Метрики по таргету обновлены.",
        reply_markup=build_manage_subscription_menu(target_id),
    )


@router.callback_query(StateFilter(SubscriptionFlow.editing_metrics), SubscriptionCallback.filter(F.action == "back_to_manage"))
async def callback_back_to_manage(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    state_data = await state.get_data()
    target_id = state_data.get("editing_target_id", "")
    await state.clear()
    await answer_or_edit(
        callback,
        "Возврат к управлению подпиской.",
        reply_markup=build_manage_subscription_menu(target_id),
    )


@router.callback_query(SubscriptionCallback.filter(F.action == "remove_target"))
async def callback_remove_target(
    callback: CallbackQuery,
    callback_data: SubscriptionCallback,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    removed = services.subscriptions.remove_target_subscription(current_user.user_id, callback_data.target_id)
    text = "🗑 Таргет удален из ваших подписок." if removed else "Подписка на таргет не найдена."
    await answer_or_edit(
        callback,
        text,
        reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN),
    )
