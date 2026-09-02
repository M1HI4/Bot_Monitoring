from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.services.users.service import UsersService


class AccessMiddleware(BaseMiddleware):
    def __init__(self, users_service: UsersService) -> None:
        self.users_service = users_service

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = None
        chat_id = None
        text = ""

        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            chat_id = event.chat.id
            text = event.text or ""
        elif isinstance(event, CallbackQuery) and event.message:
            user_id = event.from_user.id if event.from_user else None
            chat_id = event.message.chat.id

        if user_id is None or chat_id is None:
            return await handler(event, data)

        current_user = self.users_service.get_user(user_id=user_id, chat_id=chat_id)
        if current_user is None:
            command_name = text.split(maxsplit=1)[0] if text else ""
            if isinstance(event, Message) and (command_name.startswith("/start") or command_name.startswith("/help")):
                data["current_user"] = None
                return await handler(event, data)
            if isinstance(event, Message):
                await event.answer("⛔ Доступ запрещен. Пользователь не найден в whitelist.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Доступ запрещен. Пользователь не найден в whitelist.", show_alert=True)
            return None

        data["current_user"] = current_user
        return await handler(event, data)
