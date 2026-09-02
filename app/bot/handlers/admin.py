from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.callbacks import AdminCallback
from app.bot.handlers.common import build_health_text
from app.bot.handlers.helpers import answer_or_edit
from app.bot.keyboards.menus import build_admin_menu, build_admin_role_menu, build_admin_user_list
from app.bot.states.admin import AdminFlow
from app.container import AppServices
from app.models.common import Role
from app.models.config import UserDefinition
from app.utils.formatting import format_users

router = Router(name="admin")


def format_admin_user_label(user: UserDefinition | None, user_id: int) -> str:
    if user is None:
        return f"user_id={user_id}"
    username = f"@{user.username}" if user.username else "без username"
    return f"{username} (user_id={user.user_id}, role={user.role.value})"


def parse_add_user_payload(text: str) -> tuple[int, int, Role, str | None]:
    parts = text.split()
    if len(parts) < 3:
        raise ValueError("Нужно указать: user_id chat_id role [username]")
    user_id = int(parts[0])
    chat_id = int(parts[1])
    role = Role(parts[2].lower())
    username = parts[3].lstrip("@") if len(parts) > 3 else None
    return user_id, chat_id, role, username


@router.message(Command("admin_add_user"))
async def command_admin_add_user(
    message: Message,
    command: CommandObject,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    services.users.require_admin(current_user)
    if not command.args:
        await message.answer("Использование: /admin_add_user <user_id> <chat_id> <role> [username]")
        return
    try:
        user_id, chat_id, role, username = parse_add_user_payload(command.args)
    except (ValueError, TypeError) as exc:
        await message.answer(f"Некорректные аргументы: {exc}")
        return
    user = services.users.add_user(user_id=user_id, chat_id=chat_id, role=role, username=username)
    await message.answer(
        f"✅ Пользователь добавлен/обновлен: user_id={user.user_id}, chat_id={user.chat_id}, role={user.role.value}"
    )


@router.message(Command("admin_remove_user"))
async def command_admin_remove_user(
    message: Message,
    command: CommandObject,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    services.users.require_admin(current_user)
    if not command.args:
        await message.answer("Использование: /admin_remove_user <user_id>")
        return
    try:
        user_id = int(command.args)
    except ValueError:
        await message.answer("Некорректный user_id.")
        return
    user = services.users.get_by_user_id(user_id)
    removed = services.users.remove_user(user_id)
    if removed:
        services.subscriptions.clear_user(user_id)
    await message.answer(
        f"🗑 Пользователь удален: {format_admin_user_label(user, user_id)}." if removed else "Пользователь не найден."
    )


@router.message(Command("admin_set_role"))
async def command_admin_set_role(
    message: Message,
    command: CommandObject,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    services.users.require_admin(current_user)
    if not command.args:
        await message.answer("Использование: /admin_set_role <user_id> <admin|user>")
        return
    parts = command.args.split()
    if len(parts) != 2:
        await message.answer("Использование: /admin_set_role <user_id> <admin|user>")
        return
    try:
        user_id = int(parts[0])
        role = Role(parts[1].lower())
    except (ValueError, TypeError):
        await message.answer("Некорректные аргументы. Нужны: <user_id> <admin|user>.")
        return
    updated = services.users.set_role(user_id=user_id, role=role)
    await message.answer(f"🔐 Роль обновлена: user_id={updated.user_id}, role={updated.role.value}")


@router.callback_query(AdminCallback.filter(F.action == "menu"))
async def callback_admin_menu(callback: CallbackQuery, current_user: UserDefinition, services: AppServices) -> None:
    services.users.require_admin(current_user)
    await answer_or_edit(callback, "🛠 <b>Админ-панель</b>", reply_markup=build_admin_menu())


@router.callback_query(AdminCallback.filter(F.action == "users"))
async def callback_admin_users(callback: CallbackQuery, current_user: UserDefinition, services: AppServices) -> None:
    services.users.require_admin(current_user)
    text = format_users(services.users.list_users(), "👥 <b>Все пользователи</b>")
    await answer_or_edit(callback, text, reply_markup=build_admin_menu())


@router.callback_query(AdminCallback.filter(F.action == "whitelist"))
async def callback_admin_whitelist(callback: CallbackQuery, current_user: UserDefinition, services: AppServices) -> None:
    services.users.require_admin(current_user)
    text = format_users(services.users.list_whitelist(), "✅ <b>Whitelist</b>")
    await answer_or_edit(callback, text, reply_markup=build_admin_menu())


@router.callback_query(AdminCallback.filter(F.action == "add_prompt"))
async def callback_admin_add_prompt(
    callback: CallbackQuery,
    current_user: UserDefinition,
    services: AppServices,
    state: FSMContext,
) -> None:
    services.users.require_admin(current_user)
    await state.set_state(AdminFlow.waiting_add_user)
    await answer_or_edit(
        callback,
        "Введите данные пользователя в формате:\n<code>user_id chat_id role [username]</code>\n"
        "Пример: <code>632306300 632306300 admin my_login</code>",
        reply_markup=build_admin_menu(),
    )


@router.message(StateFilter(AdminFlow.waiting_add_user))
async def message_admin_add_user(
    message: Message,
    current_user: UserDefinition,
    services: AppServices,
    state: FSMContext,
) -> None:
    services.users.require_admin(current_user)
    try:
        user_id, chat_id, role, username = parse_add_user_payload(message.text or "")
    except (ValueError, TypeError) as exc:
        await message.answer(
            f"Некорректный формат: {exc}\n"
            "Ожидаю строку вида: <code>user_id chat_id role [username]</code>",
            reply_markup=build_admin_menu(),
        )
        return
    user = services.users.add_user(user_id=user_id, chat_id=chat_id, role=role, username=username)
    await state.clear()
    await message.answer(
        f"✅ Пользователь сохранен: user_id={user.user_id}, chat_id={user.chat_id}, role={user.role.value}",
        reply_markup=build_admin_menu(),
    )


@router.callback_query(AdminCallback.filter(F.action == "remove_menu"))
async def callback_admin_remove_menu(
    callback: CallbackQuery,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    services.users.require_admin(current_user)
    await answer_or_edit(
        callback,
        "Выберите пользователя для удаления из whitelist.",
        reply_markup=build_admin_user_list(services.users.list_users(), action="remove_user"),
    )


@router.callback_query(AdminCallback.filter(F.action == "remove_user"))
async def callback_admin_remove_user(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    services.users.require_admin(current_user)
    user = services.users.get_by_user_id(callback_data.user_id)
    removed = services.users.remove_user(callback_data.user_id)
    if removed:
        services.subscriptions.clear_user(callback_data.user_id)
    await answer_or_edit(
        callback,
        f"🗑 Пользователь удален: {format_admin_user_label(user, callback_data.user_id)}." if removed else "Пользователь не найден.",
        reply_markup=build_admin_menu(),
    )


@router.callback_query(AdminCallback.filter(F.action == "role_menu"))
async def callback_admin_role_menu(
    callback: CallbackQuery,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    services.users.require_admin(current_user)
    await answer_or_edit(
        callback,
        "Выберите пользователя для смены роли.",
        reply_markup=build_admin_user_list(services.users.list_users(), action="role_user"),
    )


@router.callback_query(AdminCallback.filter(F.action == "role_user"))
async def callback_admin_role_user(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    services.users.require_admin(current_user)
    user = services.users.get_by_user_id(callback_data.user_id)
    if user is None:
        await answer_or_edit(callback, "Пользователь не найден.", reply_markup=build_admin_menu())
        return
    await answer_or_edit(
        callback,
        f"Текущая роль пользователя {format_admin_user_label(user, user.user_id)}: <b>{user.role.value}</b>",
        reply_markup=build_admin_role_menu(user.user_id),
    )


@router.callback_query(AdminCallback.filter(F.action == "set_role"))
async def callback_admin_set_role(
    callback: CallbackQuery,
    callback_data: AdminCallback,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    services.users.require_admin(current_user)
    updated = services.users.set_role(user_id=callback_data.user_id, role=Role(callback_data.role))
    await answer_or_edit(
        callback,
        f"🔐 Роль пользователя {format_admin_user_label(updated, updated.user_id)} изменена на <b>{updated.role.value}</b>.",
        reply_markup=build_admin_menu(),
    )


@router.callback_query(AdminCallback.filter(F.action == "reload"))
async def callback_admin_reload(callback: CallbackQuery, current_user: UserDefinition, services: AppServices) -> None:
    services.users.require_admin(current_user)
    services.config.ensure_runtime_files()
    diagnostics = services.config.validate_all()
    await answer_or_edit(
        callback,
        "🔄 Конфиги успешно перечитаны.\n"
        f"Targets: {diagnostics['targets']}\n"
        f"Users: {diagnostics['users']}\n"
        f"Alert metrics: {diagnostics['alert_metrics']}\n"
        f"Subscriptions: {diagnostics['subscriptions']}",
        reply_markup=build_admin_menu(),
    )


@router.callback_query(AdminCallback.filter(F.action == "prometheus"))
async def callback_admin_prometheus(
    callback: CallbackQuery,
    current_user: UserDefinition,
    services: AppServices,
) -> None:
    services.users.require_admin(current_user)
    ok, detail = await services.monitoring.get_prometheus_health()
    text = "📡 Prometheus доступен." if ok else "📡 Prometheus недоступен."
    await answer_or_edit(callback, f"{text}\n{detail}", reply_markup=build_admin_menu())


@router.callback_query(AdminCallback.filter(F.action == "health"))
async def callback_admin_health(callback: CallbackQuery, current_user: UserDefinition, services: AppServices) -> None:
    services.users.require_admin(current_user)
    await answer_or_edit(callback, await build_health_text(services), reply_markup=build_admin_menu())
