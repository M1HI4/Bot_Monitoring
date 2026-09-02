from aiogram.fsm.state import State, StatesGroup


class AdminFlow(StatesGroup):
    waiting_add_user = State()
