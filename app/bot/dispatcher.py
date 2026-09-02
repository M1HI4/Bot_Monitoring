from __future__ import annotations

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers.admin import router as admin_router
from app.bot.handlers.common import router as common_router
from app.bot.handlers.subscriptions import router as subscriptions_router
from app.bot.handlers.summaries import router as summaries_router
from app.bot.middlewares.access import AccessMiddleware
from app.bot.middlewares.chat_guard import PrivateChatMiddleware
from app.container import AppServices


def build_dispatcher(services: AppServices) -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.message.outer_middleware(PrivateChatMiddleware())
    dispatcher.callback_query.outer_middleware(PrivateChatMiddleware())
    dispatcher.message.outer_middleware(AccessMiddleware(services.users))
    dispatcher.callback_query.outer_middleware(AccessMiddleware(services.users))
    dispatcher.include_router(common_router)
    dispatcher.include_router(subscriptions_router)
    dispatcher.include_router(summaries_router)
    dispatcher.include_router(admin_router)
    return dispatcher
