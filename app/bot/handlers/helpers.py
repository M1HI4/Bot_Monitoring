from __future__ import annotations

from collections.abc import Awaitable

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message


async def answer_or_edit(
    target: Message | CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text=text, reply_markup=reply_markup)
        except TelegramBadRequest:
            await target.message.answer(text=text, reply_markup=reply_markup)
        await target.answer()
        return
    await target.answer(text=text, reply_markup=reply_markup)


async def run_with_user_feedback(
    action: Awaitable[str],
    target: Message | CallbackQuery,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    text = await action
    await answer_or_edit(target, text=text, reply_markup=reply_markup)
