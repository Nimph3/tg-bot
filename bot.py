import asyncio
import aiohttp
import csv
import io

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart


API_TOKEN = "7973176325:AAFblXm7-SE3aZwtk2j70dupKJ4CIKC74Ow"

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/17iHtFw9e_IsKDDksdv4fAbIuOuLkLPxVeYlyi6Db_lY/export?format=csv&gid=1405588358"

PARALLELS = ["5", "6", "7", "8", "9", "10", "11"]
CLASS_LETTERS = ["А", "Б", "В", "Г"]

bot = Bot(API_TOKEN)
dp = Dispatcher()

# Настройки пользователей: какой класс выбрал
user_settings: dict[int, dict[str, str]] = {}
# что сейчас выбирает пользователь
user_state: dict[int, str] = {}

MAX_MESSAGE_LENGTH = 4000

async def send_long_text(message, text: str):
    """
    обходим лимит телеги на символы
    """
    if len(text) <= MAX_MESSAGE_LENGTH:
        await message.answer(text)
        return

    current_chunk = ""

    for line in text.splitlines(keepends=True):  # режем по строкам
        # Если следующая строка не влезает в текущий кусок — отправляем кусок
        if len(current_chunk) + len(line) > MAX_MESSAGE_LENGTH:
            await message.answer(current_chunk)
            current_chunk = ""
        current_chunk += line

    # последний кусок
    if current_chunk:
        await message.answer(current_chunk)

def make_parallel_keyboard() -> ReplyKeyboardMarkup:
    """
    кнопки для выбора параллели (5, 6, 7 и тд)
    """
    rows = []
    row = []
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
        one_time_keyboard=True
    )


def make_class_letter_keyboard() -> ReplyKeyboardMarkup:
    """
    кнопки для выбора буквы класса (А, Б, В и тд)
    """
    row = [KeyboardButton(text=letter) for letter in CLASS_LETTERS]
    return ReplyKeyboardMarkup(
        keyboard=[row],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def make_main_menu() -> ReplyKeyboardMarkup:
    """ Главное меню после того, как класс выбран """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Расписание")],
            [KeyboardButton(text="🔁 Сменить класс")]
        ],
        resize_keyboard=True
    )


async def get_schedule_for_class(parallel: str, letter: str) -> str:
    """
    Читает CSV из Google-таблицы и достаёт расписание для конкретного класса.
    Ожидается, что в таблице есть как минимум столбцы:
    Класс, День, Урок, Предмет, Кабинет (названия можно поменять в коде).
    """
    class_code = f"{parallel}{letter}"

    # 1. Тянем CSV-текст
    async with aiohttp.ClientSession() as session:
        async with session.get(SHEET_CSV_URL) as resp:
            resp.raise_for_status()
            csv_text = await resp.text()

    # На всякий случай защита от HTML вместо CSV
    if csv_text.lstrip().startswith("<"):
        return "Ошибка: Google вернул HTML-страницу, а не CSV.\n" \
               "Проверь, что ссылка ок (export?format=csv&gid=...) и что у таблицы доступ «по ссылке»."

    # 2. Парсим CSV в список словарей
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)

    # 3. Фильтруем строки только по нашему классу
    class_rows = [row for row in rows if row.get("Класс") == class_code]

    if not class_rows:
        return f"Для класса {class_code} расписание в таблице не найдено."

    # 4. Собираем текст: сгруппируем по дню недели, чтобы не было каши
    # Можно задать порядок дней, если хочешь красиво
    day_order = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
    day_to_lessons: dict[str, list[str]] = {}

    for row in class_rows:
        day = (row.get("День") or "").strip()
        lesson_num = (row.get("Урок") or "").strip()
        subject = (row.get("Предмет") or "").strip()
        room = (row.get("Кабинет") or "").strip()

        # строка вида "1. Математика (каб. 201)"
        line = lesson_num + ". " + subject
        if room:
            line += f" (каб. {room})"

        day_to_lessons.setdefault(day, []).append(line)

    # 5. Формируем финальный текст
    lines: list[str] = [f"Расписание для класса {class_code}:\n"]

    # Сначала дни в заданном порядке, потом всё, что не попало (если есть странные значения)
    used_days = set()
    for day in day_order:
        if day in day_to_lessons:
            used_days.add(day)
            lines.append(f"{day}:")
            for lesson_line in day_to_lessons[day]:
                lines.append("  " + lesson_line)
            lines.append("")  # пустая строка между днями

    for day, lessons in day_to_lessons.items():
        if day in used_days:
            continue
        lines.append(f"{day}:")
        for lesson_line in lessons:
            lines.append("  " + lesson_line)
        lines.append("")

    return "\n".join(lines).strip()



@dp.message(CommandStart())
async def cmd_start(message: Message):
    chat_id = message.chat.id

    # Просим выбрать параллель
    user_state[chat_id] = "choose_parallel"
    user_settings.setdefault(chat_id, {})

    await message.answer(
        "Привет! Я бот с расписанием школы.\n"
        "Сначала выбери свою параллель:",
        reply_markup=make_parallel_keyboard()
    )


@dp.message(F.text.in_(PARALLELS))
async def handle_parallel(message: Message):
    """ Обработка выбора параллели """
    chat_id = message.chat.id

    # Реагируем только если человек сейчас на этапе выбора параллели
    if user_state.get(chat_id) != "choose_parallel":
        # Если он уже всё выбрал, лучше не путать
        await message.answer(
            "Ты уже выбирал параллель. Если хочешь изменить класс — нажми «🔁 Сменить класс»."
        )
        return

    parallel = message.text
    user_settings.setdefault(chat_id, {})["parallel"] = parallel
    user_state[chat_id] = "choose_letter"

    await message.answer(
        f"Ок, параллель {parallel}.\n"
        f"Теперь выбери букву своего класса:",
        reply_markup=make_class_letter_keyboard()
    )


@dp.message(F.text.in_(CLASS_LETTERS))
async def handle_class_letter(message: Message):
    """ Обработка выбора буквы класса """
    chat_id = message.chat.id

    if user_state.get(chat_id) != "choose_letter":
        await message.answer(
            "Сначала нужно выбрать параллель.\nНапиши /start, чтобы начать заново."
        )
        return

    letter = message.text
    settings = user_settings.setdefault(chat_id, {})
    settings["class_letter"] = letter

    parallel = settings.get("parallel", "?")
    user_state[chat_id] = "ready"

    await message.answer(
        f"Класс сохранён: {parallel}{letter}.\n"
        f"Теперь можешь получать своё расписание.",
        reply_markup=make_main_menu()
    )


@dp.message(F.text == "🔁 Сменить класс")
async def change_class(message: Message):
    """ юзер захотел поменять свой класс """
    chat_id = message.chat.id
    user_state[chat_id] = "choose_parallel"

    await message.answer(
        "Ок, давай выберем класс заново.\nСначала ПАРАЛЛЕЛЬ:",
        reply_markup=make_parallel_keyboard()
    )


@dp.message(F.text == "📅 Расписание")
async def send_schedule(message: Message):
    """ Отправляем расписание для выбранного класса """
    chat_id = message.chat.id
    settings = user_settings.get(chat_id, {})
    parallel = settings.get("parallel")
    letter = settings.get("class_letter")

    if not parallel or not letter or user_state.get(chat_id) != "ready":
        # Если ещё не выбрал класс
        user_state[chat_id] = "choose_parallel"
        await message.answer(
            "Сначала нужно выбрать свою параллель и букву класса.\n"
            "Начнём с параллели:",
            reply_markup=make_parallel_keyboard()
        )
        return

    schedule_text = await get_schedule_for_class(parallel, letter)
    await send_long_text(message, schedule_text)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())