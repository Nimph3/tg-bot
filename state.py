from typing import Dict, Set, TypedDict

from aiogram.fsm.state import State, StatesGroup

from storage import load_state, save_state as _save_state


class UserSettings(TypedDict, total=False):
    # Профиль
    first_name: str
    last_name: str

    # Свой класс
    parallel: str
    variant: str

    # Чужой класс, сорри хищника нет
    other_parallel: str
    other_variant: str


class UserStates(StatesGroup):
    # Регистрация
    registering_name = State()
    registering_surname = State()

    # Выбор своего класса
    choosing_my_class = State()
    choosing_my_variant = State()

    # Выбор чужого класса
    choosing_other_class = State()
    choosing_other_variant = State()

    # Главное меню
    idle = State()


_loaded_user_settings, _loaded_known_users = load_state()

user_settings = {chat_id: settings for chat_id, settings in _loaded_user_settings.items()}
known_users = set(_loaded_known_users)


def save_state() -> None:
    # Сохранить user settings и known users в JSON.
    _save_state({k: dict(v) for k, v in user_settings.items()}, set(known_users))
