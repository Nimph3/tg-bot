import random

from aiogram.types import Message

from config import ADMIN_IDS, MAX_MESSAGE_LENGTH


def normalize_spaces(s: str) -> str:
    return " ".join(s.split())


async def send_long_text(message: Message, text: str) -> None:
    # Разбиваем по строкам, чтобы не рвать дни, уроки.
    if len(text) <= MAX_MESSAGE_LENGTH:
        await message.answer(text)
        return

    current_chunk = ""

    for line in text.splitlines(keepends=True):
        if len(current_chunk) + len(line) > MAX_MESSAGE_LENGTH:
            await message.answer(current_chunk)
            current_chunk = ""
        current_chunk += line

    if current_chunk:
        await message.answer(current_chunk)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

FREE_TIME_TEXTS = [
    "Можно поспать 😴",
    "Самое время перекусить 🍔",
    "Можно погулять 🏃‍♂️",
    "Чилл, уроков нет 😌",
    "Идеальное время поиграть 🎮",
    "Свободное окно ✨",
    "Можно просто ничего не делать 🫙",
    "Время для творчества 🎨",
]


def get_free_time_text() -> str:
    return random.choice(FREE_TIME_TEXTS)
