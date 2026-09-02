from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.bot.callbacks import SummaryCallback
from app.bot.handlers.helpers import answer_or_edit
from app.bot.keyboards.menus import build_main_menu, build_summary_menu
from app.container import AppServices
from app.models.common import Role
from app.models.config import TargetDefinition, UserDefinition
from app.utils.formatting import format_target_summary

router = Router(name="summaries")


def get_user_summary_scope(
    current_user: UserDefinition,
    services: AppServices,
) -> tuple[list[TargetDefinition], dict[str, list]]:
    user_subscription = services.subscriptions.get_user_subscription(current_user.user_id)
    if user_subscription is None or not user_subscription.targets:
        return [], {}
    targets_map = services.monitoring.get_targets_map()
    metrics_map = {item.target_id: item.metrics for item in user_subscription.targets}
    targets = [targets_map[item.target_id] for item in user_subscription.targets if item.target_id in targets_map]
    return targets, metrics_map


async def show_summary_menu(
    target: Message | CallbackQuery,
    *,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    user_subscription = services.subscriptions.get_user_subscription(current_user.user_id)
    targets_by_id = services.monitoring.get_targets_map()
    await answer_or_edit(
        target,
        "📊 <b>Сводка</b>\nВыберите один таргет или получите сводку по всем своим подпискам.",
        reply_markup=build_summary_menu(user_subscription, targets_by_id),
    )


@router.message(Command("summary"))
async def command_summary(message: Message, current_user: UserDefinition, services: AppServices) -> None:
    await show_summary_menu(message, current_user=current_user, services=services)


@router.callback_query(SummaryCallback.filter(F.action == "menu"))
async def callback_summary_menu(callback: CallbackQuery, current_user: UserDefinition, services: AppServices) -> None:
    await show_summary_menu(callback, current_user=current_user, services=services)


@router.callback_query(SummaryCallback.filter(F.action == "all"))
async def callback_summary_all(callback: CallbackQuery, current_user: UserDefinition, services: AppServices) -> None:
    targets, metrics_map = get_user_summary_scope(current_user, services)
    if not targets:
        await answer_or_edit(
            callback,
            "📭 У вас нет подписок для построения сводки.",
            reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN),
        )
        return
    snapshots = await services.monitoring.get_many_target_snapshots(targets, metrics_map=metrics_map)
    timezone_name = services.config.load_runtime_config().app.timezone
    text = "\n\n".join(format_target_summary(snapshot, timezone_name) for snapshot in snapshots.values())
    await answer_or_edit(
        callback,
        text,
        reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN),
    )


@router.callback_query(SummaryCallback.filter(F.action == "one"))
async def callback_summary_one(
    callback: CallbackQuery,
    callback_data: SummaryCallback,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    user_subscription = services.subscriptions.get_user_subscription(current_user.user_id)
    if user_subscription is None:
        await answer_or_edit(
            callback,
            "📭 У вас нет подписок.",
            reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN),
        )
        return
    target_subscription = next((item for item in user_subscription.targets if item.target_id == callback_data.target_id), None)
    target = services.monitoring.get_target_by_id(callback_data.target_id)
    if target_subscription is None or target is None:
        await answer_or_edit(
            callback,
            "⚠️ Таргет недоступен или отсутствует в ваших подписках.",
            reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN),
        )
        return
    snapshot = await services.monitoring.get_target_snapshot(target, metrics=target_subscription.metrics)
    timezone_name = services.config.load_runtime_config().app.timezone
    await answer_or_edit(
        callback,
        format_target_summary(snapshot, timezone_name),
        reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN),
    )
