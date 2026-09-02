from aiogram.fsm.state import State, StatesGroup


class SubscriptionFlow(StatesGroup):
    selecting_targets = State()
    selecting_metrics = State()
    editing_metrics = State()
