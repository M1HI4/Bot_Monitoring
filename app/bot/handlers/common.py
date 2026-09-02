from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, ErrorEvent, Message

from app.bot.callbacks import MenuCallback
from app.bot.handlers.helpers import answer_or_edit
from app.bot.keyboards.menus import build_admin_menu, build_main_menu
from app.container import AppServices
from app.models.common import Role
from app.models.config import UserDefinition
from app.utils.exceptions import AccessDeniedError, ConfigValidationError, MetricUnavailableError, PrometheusRequestError
from app.utils.formatting import format_health_report, format_metric_catalog, format_target_list

router = Router(name="common")


async def build_health_text(services: AppServices) -> str:
    try:
        config_summary_data = services.config.validate_all()
        bot_ok = True
        config_summary = (
            f"ok, targets={config_summary_data['targets']}, users={config_summary_data['users']}, "
            f"alert_metrics={config_summary_data['alert_metrics']}, subs={config_summary_data['subscriptions']}"
        )
        users_count = config_summary_data["users"]
        targets_count = config_summary_data["targets"]
        subscriptions_count = services.subscriptions.get_total_target_subscriptions()
    except Exception as exc:
        bot_ok = False
        config_summary = f"ошибка: {exc}"
        users_count = 0
        targets_count = 0
        subscriptions_count = 0

    prometheus_ok, prometheus_detail = await services.monitoring.get_prometheus_health()
    report = format_health_report(
        bot_ok=bot_ok,
        prometheus_ok=prometheus_ok,
        config_summary=config_summary,
        users_count=users_count,
        targets_count=targets_count,
        subscriptions_count=subscriptions_count,
    )
    return f"{report}\n📝 {prometheus_detail}"


@router.message(CommandStart())
async def command_start(message: Message, current_user: UserDefinition | None, services: AppServices) -> None:
    if current_user is None:
        await message.answer(
            "⛔ Доступ запрещен.\nБот работает только для пользователей из whitelist и только в личном чате."
        )
        return
    is_admin = current_user.role == Role.ADMIN
    await message.answer(
        "Добро пожаловать в закрытый бот мониторинга Prometheus.\n"
        "Используйте меню ниже для подписок, сводок и проверки состояния.",
        reply_markup=build_main_menu(is_admin=is_admin),
    )


@router.message(Command("help"))
async def command_help(message: Message, current_user: UserDefinition | None) -> None:
    if current_user is None:
        await message.answer(
            "⛔ Доступ закрыт. Для работы нужны private chat и запись в whitelist.\n"
            "Доступные публичные команды: /start, /help."
        )
        return
    text = (
        "ℹ️ <b>Команды</b>\n"
        "/start - открыть главное меню.\n"
        "/help - показать справку.\n"
        "/targets - список таргетов.\n"
        "/metrics - список метрик.\n"
        "/subscribe - начать выбор таргетов и метрик.\n"
        "/subscriptions - показать мои подписки.\n"
        "/unsubscribe - открыть меню удаления подписок.\n"
        "/summary - открыть меню сводки.\n"
        "/status - статус бота и Prometheus.\n"
        "/health - healthcheck.\n"
        "/reload - перечитать конфиги (admin).\n"
        "/admin - открыть админ-панель (admin)."
    )
    await message.answer(text, reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN))


@router.message(Command("targets"))
async def command_targets(message: Message, current_user: UserDefinition, services: AppServices) -> None:
    targets = services.monitoring.get_enabled_targets()
    await message.answer(
        format_target_list(targets) if targets else "📭 В конфиге нет включенных таргетов.",
        reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN),
    )


@router.message(Command("metrics"))
async def command_metrics(message: Message, current_user: UserDefinition) -> None:
    text = (
        f"{format_metric_catalog()}\n\n"
        "Типы таргетов:\n"
        "• physical - доступны CPU, RAM, диск, температура.\n"
        "• blade - доступны CPU, RAM, диск, температура.\n"
        "• vm - доступны CPU, RAM, диск.\n"
        "• container - доступны CPU, RAM, диск из cAdvisor."
    )
    await message.answer(text, reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN))


@router.message(Command("health"))
async def command_health(message: Message, current_user: UserDefinition, services: AppServices) -> None:
    await message.answer(await build_health_text(services), reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN))


@router.message(Command("status"))
async def command_status(message: Message, current_user: UserDefinition, services: AppServices) -> None:
    await message.answer(await build_health_text(services), reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN))


@router.message(Command("reload"))
async def command_reload(message: Message, current_user: UserDefinition, services: AppServices) -> None:
    services.users.require_admin(current_user)
    services.config.ensure_runtime_files()
    diagnostics = services.config.validate_all()
    await message.answer(
        "🔄 Конфиги успешно перечитаны.\n"
        f"Targets: {diagnostics['targets']}\n"
        f"Users: {diagnostics['users']}\n"
        f"Alert metrics: {diagnostics['alert_metrics']}\n"
        f"Subscriptions: {diagnostics['subscriptions']}",
        reply_markup=build_main_menu(is_admin=True),
    )


@router.message(Command("admin"))
async def command_admin(message: Message, current_user: UserDefinition, services: AppServices) -> None:
    services.users.require_admin(current_user)
    await message.answer("🛠 <b>Админ-панель</b>", reply_markup=build_admin_menu())


@router.callback_query(MenuCallback.filter())
async def callback_menu(
    callback: CallbackQuery,
    callback_data: MenuCallback,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    if callback_data.page == "main":
        await answer_or_edit(
            callback,
            "Главное меню.",
            reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN),
        )
        return
    if callback_data.page == "targets":
        targets = services.monitoring.get_enabled_targets()
        await answer_or_edit(
            callback,
            format_target_list(targets) if targets else "📭 В конфиге нет включенных таргетов.",
            reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN),
        )
        return
    if callback_data.page == "metrics":
        await answer_or_edit(
            callback,
            f"{format_metric_catalog()}\n\n"
            "Для vm и container метрика temperature недоступна.\n"
            "Для container CPU, RAM и диск берутся из cAdvisor.",
            reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN),
        )
        return
    if callback_data.page in {"health", "status"}:
        await answer_or_edit(
            callback,
            await build_health_text(services),
            reply_markup=build_main_menu(is_admin=current_user.role == Role.ADMIN),
        )
        return
    if callback_data.page == "reload":
        services.config.ensure_runtime_files()
        diagnostics = services.config.validate_all()
        if current_user.role != Role.ADMIN:
            await answer_or_edit(
                callback,
                "🔄 Меню обновлено, конфиги успешно перечитаны.",
                reply_markup=build_main_menu(is_admin=False),
            )
            return
        await answer_or_edit(
            callback,
            "🔄 Конфиги успешно перечитаны.\n"
            f"Targets: {diagnostics['targets']}\n"
            f"Users: {diagnostics['users']}\n"
            f"Alert metrics: {diagnostics['alert_metrics']}\n"
            f"Subscriptions: {diagnostics['subscriptions']}",
            reply_markup=build_main_menu(is_admin=True),
        )
        return
    if callback_data.page == "admin":
        services.users.require_admin(current_user)
        await answer_or_edit(callback, "🛠 <b>Админ-панель</b>", reply_markup=build_admin_menu())


@router.error()
async def global_error_handler(event: ErrorEvent) -> bool:
    exception = event.exception
    if isinstance(exception, AccessDeniedError):
        text = f"⛔ {exception}"
    elif isinstance(exception, ConfigValidationError):
        text = f"⚠️ Ошибка конфигурации: {exception}"
    elif isinstance(exception, PrometheusRequestError):
        text = f"📡 {exception}"
    elif isinstance(exception, MetricUnavailableError):
        text = f"📈 {exception}"
    else:
        text = f"⚠️ Внутренняя ошибка: {exception}"

    if event.update.message:
        await event.update.message.answer(text)
    elif event.update.callback_query:
        await event.update.callback_query.answer("Произошла ошибка.", show_alert=True)
        if event.update.callback_query.message:
            await event.update.callback_query.message.answer(text)
    return True
