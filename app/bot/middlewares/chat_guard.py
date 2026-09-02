from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class PrivateChatMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat = None
        if isinstance(event, Message):
            chat = event.chat
        elif isinstance(event, CallbackQuery) and event.message:
            chat = event.message.chat

        if chat is not None and chat.type != "private":
            if isinstance(event, Message):
                await event.answer("⛔ Бот работает только в личном чате Telegram.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Бот работает только в личном чате Telegram.", show_alert=True)
            return None
        return await handler(event, data)
