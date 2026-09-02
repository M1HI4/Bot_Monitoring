from __future__ import annotations

from typing import Optional

from aiogram.filters.callback_data import CallbackData


class MenuCallback(CallbackData, prefix="menu"):
    page: str
    target_id: Optional[str] = None
    extra: Optional[str] = None


class SubscriptionCallback(CallbackData, prefix="sub"):
    action: str
    target_id: Optional[str] = None
    metric: Optional[str] = None
    target_type: Optional[str] = None


class SummaryCallback(CallbackData, prefix="sum"):
    action: str
    target_id: Optional[str] = None


class AdminCallback(CallbackData, prefix="adm"):
    action: str
    user_id: Optional[int] = None
    role: Optional[str] = None
