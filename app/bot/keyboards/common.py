from __future__ import annotations

from aiogram.types import InlineKeyboardButton

from app.bot.callbacks import MenuCallback


def back_button(page: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text="Назад", callback_data=MenuCallback(page=page).pack())


def home_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="Домой", callback_data=MenuCallback(page="main").pack())


def refresh_button(page: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text="Обновить", callback_data=MenuCallback(page=page).pack())
