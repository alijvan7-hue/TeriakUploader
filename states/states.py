# states/states.py
from aiogram.fsm.state import State, StatesGroup


class UploadFile(StatesGroup):
    waiting_file = State()
    waiting_caption = State()


class SearchFile(StatesGroup):
    waiting_query = State()


class Broadcast(StatesGroup):
    waiting_message = State()


class AddAdmin(StatesGroup):
    waiting_id = State()


class RemoveAdmin(StatesGroup):
    waiting_id = State()


class BanUser(StatesGroup):
    waiting_id = State()


class UnbanUser(StatesGroup):
    waiting_id = State()


class UserInfo(StatesGroup):
    waiting_id = State()


class AddChannel(StatesGroup):
    waiting_channel = State()


class RemoveChannel(StatesGroup):
    waiting_channel = State()
