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

CLASS_VARIANTS_BY_PARALLEL: dict[str, list[str]] = {
    "5": [
        "соц-эк 1",
        "соц-эк 2",
        "соц-эк 3",
        "соц-эк 4",
        "соц-эк 5",
        "фил",
        "эко",
        "эконом 1",
        "эконом 2",
        "эконом 3",
        "эконом 4",
        "эн 1",
        "эн 2",
    ],
}

ALL_VARIANTS = sorted(
    {v for variants in CLASS_VARIANTS_BY_PARALLEL.values() for v in variants}
)

bot = Bot(API_TOKEN)
dp = Dispatcher()

# Настройки пользователей: какой класс выбрал
user_settings: dict[int, dict[str, str]] = {}
# что сейчас выбирает пользователь
user_state: dict[int, str] = {}

MAX_MESSAGE_LENGTH = 4000

def normalize_spaces(s: str) -> str:
    return " ".join(s.split())

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


def make_variant_keyboard(parallel: str) -> ReplyKeyboardMarkup:
    """
    Кнопки для выбора профиля/варианта в рамках параллели
    (соц-эк 1, соц-эк 2, фил, эко, эконом 1, …).
    """
    variants = CLASS_VARIANTS_BY_PARALLEL.get(parallel, [])
    rows: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []

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


def make_main_menu() -> ReplyKeyboardMarkup:
    """ Главное меню после того, как класс выбран """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Расписание")],
            [KeyboardButton(text="🔁 Сменить класс")]
        ],
        resize_keyboard=True
    )


async def get_schedule_for_class(parallel: str, variant: str) -> str:
    class_label = f"{parallel} {variant}"
    block_title = f"Расписание {parallel} {variant} класса"
    block_title_norm = normalize_spaces(block_title)

    # 1. Тянем CSV-текст
    async with aiohttp.ClientSession() as session:
        async with session.get(SHEET_CSV_URL) as resp:
            resp.raise_for_status()
            csv_text = await resp.text()

    # Если вдруг прилетел HTML (страница, а не CSV)
    if csv_text.lstrip().startswith("<"):
        return (
            "Ошибка: Google вернул HTML-страницу, а не CSV.\n"
            "Проверь, что ссылка вида /export?format=csv&gid=... "
            "и что у таблицы доступ «по ссылке, просмотр»."
        )

    reader = csv.reader(io.StringIO(csv_text))

    in_block = False
    header_processed = False
    day_indices: dict[str, int] = {}
    day_to_lessons: dict[str, list[str]] = {}

    day_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]

    for row in reader:
        # собираем непустые ячейки, чтобы склеить строку заголовка блока
        nonempty_cells = [cell.strip() for cell in row if cell.strip()]
        joined = " ".join(nonempty_cells)
        joined_norm = normalize_spaces(joined) if joined else ""

        if not in_block:
            # Ищем нашу строку вида "Расписание 5 соц-эк 1 класса"
            if joined_norm and joined_norm.startswith(block_title_norm):
                in_block = True
                header_processed = False
                day_indices = {}
            continue

        # Уже внутри нужного блока

        # Если наткнулись на заголовок другого блока — выходим
        if (
            joined_norm.startswith("Расписание ")
            and "класса" in joined_norm
            and not joined_norm.startswith(block_title_norm)
        ):
            break

        # Ищем шапку мини-таблицы: строка с "№ урока" и днями недели
        if not header_processed and any("№ урока" in cell for cell in row):
            day_indices = {}
            for idx, cell in enumerate(row):
                name = cell.strip()
                if name in day_names:
                    day_indices[name] = idx
            header_processed = True
            continue

        # Пока шапку не нашли — пропускаем строки
        if not header_processed:
            continue

        # Строка урока: первый столбец должен быть не пустой
        if len(row) == 0 or not row[0].strip():
            continue

        lesson_cell = row[0].strip()
        parts = lesson_cell.splitlines()
        lesson_num = parts[0].strip()
        time = parts[1].strip() if len(parts) > 1 else ""

        for day, idx in day_indices.items():
            if idx >= len(row):
                continue
            subject = row[idx].strip()
            if not subject:
                continue

            line = f"{lesson_num}. {subject}"
            if time:
                line += f" ({time})"

            day_to_lessons.setdefault(day, []).append(line)

    if not day_to_lessons:
        return (
            f"Не удалось найти расписание для класса {class_label}.\n"
            f"Проверь, что в таблице есть строка с заголовком «{block_title}»."
        )

    # Собираем красивый текст
    lines: list[str] = [
        f"Расписание для класса {class_label}:",
        f"({block_title})",
        "",
    ]

    for day in day_names:
        lessons = day_to_lessons.get(day)
        if not lessons:
            continue
        lines.append(f"{day}:")
        for l in lessons:
            lines.append("  " + l)
        lines.append("")

    return "\n".join(lines).rstrip()


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
    """Обработка выбора параллели."""
    chat_id = message.chat.id

    parallel = message.text

    # если для этой параллели нет вариантов — скажем об этом
    if parallel not in CLASS_VARIANTS_BY_PARALLEL:
        await message.answer(
            f"Для параллели {parallel} расписание в боте пока не настроено."
        )
        return

    user_settings.setdefault(chat_id, {})["parallel"] = parallel
    user_state[chat_id] = "choose_variant"

    await message.answer(
        f"Ок, параллель {parallel}.\n"
        f"Теперь выбери свой класс (профиль):",
        reply_markup=make_variant_keyboard(parallel),
    )


@dp.message(F.text.in_(ALL_VARIANTS))
async def handle_variant(message: Message):
    """Обработка выбора варианта: 'соц-эк 1', 'фил', 'эко' и т.д."""
    chat_id = message.chat.id

    if user_state.get(chat_id) != "choose_variant":
        await message.answer(
            "Сначала нужно выбрать параллель.\nНапиши /start, чтобы начать заново."
        )
        return

    variant = message.text
    settings = user_settings.setdefault(chat_id, {})
    parallel = settings.get("parallel")

    if not parallel:
        user_state[chat_id] = "choose_parallel"
        await message.answer(
            "Что-то пошло не так с выбором параллели.\n"
            "Давай начнем сначала:",
            reply_markup=make_parallel_keyboard(),
        )
        return

    if variant not in CLASS_VARIANTS_BY_PARALLEL.get(parallel, []):
        await message.answer(
            f"В параллели {parallel} нет класса «{variant}».\n"
            f"Выбери из предложенных вариантов."
        )
        return

    settings["variant"] = variant
    user_state[chat_id] = "ready"

    await message.answer(
        f"Класс сохранён: {parallel} {variant}.\n"
        f"Теперь можешь получать своё расписание.",
        reply_markup=make_main_menu(),
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
    """Отправляем расписание для выбранного класса."""
    chat_id = message.chat.id
    settings = user_settings.get(chat_id, {})
    parallel = settings.get("parallel")
    variant = settings.get("variant")

    if not parallel or not variant or user_state.get(chat_id) != "ready":
        user_state[chat_id] = "choose_parallel"
        await message.answer(
            "Сначала нужно выбрать свою параллель и профиль класса.\n"
            "Начнём с параллели:",
            reply_markup=make_parallel_keyboard(),
        )
        return

    schedule_text = await get_schedule_for_class(parallel, variant)
    await send_long_text(message, schedule_text)

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())