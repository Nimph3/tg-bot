from typing import List

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from config import CLASS_VARIANTS_BY_PARALLEL, PARALLELS


def make_class_keyboard() -> ReplyKeyboardMarkup:
    rows: List[List[KeyboardButton]] = []
    row: List[KeyboardButton] = []

    for i, p in enumerate(PARALLELS, start=1):
        row.append(KeyboardButton(text=p))
        if i % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def make_parallel_keyboard(class_number: str) -> ReplyKeyboardMarkup:
    variants = CLASS_VARIANTS_BY_PARALLEL.get(class_number, [])
    rows: List[List[KeyboardButton]] = []
    row: List[KeyboardButton] = []

    for i, v in enumerate(variants, start=1):
        row.append(KeyboardButton(text=v))
        if i % 3 == 0:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def make_main_menu(has_other: bool = False) -> ReplyKeyboardMarkup:
    buttons: List[List[KeyboardButton]] = [
        [
            KeyboardButton(text="📅 На сегодня"),
            KeyboardButton(text="📅 На завтра"),
        ],
        [KeyboardButton(text="📅 На неделю")],
    ]

    if has_other:
        buttons.append([KeyboardButton(text="📅 Расписание выбранного класса")])

    buttons.append([KeyboardButton(text="👀 Расписание другого класса")])
    buttons.append([KeyboardButton(text="🔁 Сменить класс")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
    )


def make_return_to_my_schedule_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="↩️ Вернуться к своему расписанию")],
        ],
        resize_keyboard=True,
    )
