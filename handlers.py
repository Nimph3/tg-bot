import logging

from aiogram import F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import ALL_VARIANTS, CLASS_VARIANTS_BY_PARALLEL, PARALLELS
from keyboards import (
    make_class_keyboard,
    make_main_menu,
    make_parallel_keyboard,
    make_return_to_my_schedule_keyboard,
)
from loader import bot, dp
from shedule import (
    get_class_schedule,
    get_today_day_name,
    get_tomorrow_day_name,
    render_day_schedule,
    render_full_schedule,
    reset_cache,
)
from state import UserStates, known_users, user_settings, save_state
from utils import is_admin, send_long_text, get_free_time_text

logger = logging.getLogger(__name__)

async def _ensure_registered(message: Message, state: FSMContext):
    """
    Раньше бот просил отдельно регистрироваться (вводить имя и фамилию).
    Теперь считаем, что пользователь всегда "зарегистрирован":
    просто берём имя/фамилию из профиля Telegram и сохраняем в user_settings.
    """
    chat_id = message.chat.id
    settings = user_settings.setdefault(chat_id, {})

    tg_first = (message.from_user.first_name or "").strip() if message.from_user else ""
    tg_last = (message.from_user.last_name or "").strip() if message.from_user else ""

    if tg_first and not settings.get("first_name"):
        settings["first_name"] = tg_first
    if tg_last and not settings.get("last_name"):
        settings["last_name"] = tg_last

    known_users.add(chat_id)
    save_state()

    return True, settings

async def _ensure_my_class(message: Message, state: FSMContext):
    is_reg, settings = await _ensure_registered(message, state)
    if not is_reg:
        return None, None, settings

    parallel = settings.get("parallel")
    variant = settings.get("variant")

    if not parallel or not variant:
        await state.set_state(UserStates.choosing_my_class)
        await message.answer(
            "Сначала нужно выбрать свой класс.\n"
            "Выбери <b>КЛАСС</b> (цифру):",
            reply_markup=make_class_keyboard(),
        )
        return None, None, settings

    return parallel, variant, settings


# Общие команды

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    # Сразу считаем пользователя "зарегистрированным" и переходим к выбору класса.
    await _ensure_registered(message, state)

    chat_id = message.chat.id
    known_users.add(chat_id)
    settings = user_settings.setdefault(chat_id, {})

    await state.set_state(UserStates.choosing_my_class)

    # каждый /start позволяет выбрать класс заново
    settings.pop("parallel", None)
    settings.pop("variant", None)
    save_state()

    hello_name = (
        settings.get("first_name")
        or (message.from_user.first_name if message.from_user and message.from_user.first_name else None)
        or "друг"
    )

    await message.answer(
        f"Привет, {hello_name}!\n"
        f"Давай выберем твой класс.\n"
        f"Сначала выбери <b>КЛАСС</b> (цифру):",
        reply_markup=make_class_keyboard(),
    )

@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>Что я умею:</b>\n"
        "• Показывать расписание на сегодня / завтра / всю неделю\n"
        "• Давать расписание другого класса\n"
        "• Сохранять твой класс и профиль\n\n"
        "Сначала нужно выбрать свой класс через /start.\n"
        "Имя и фамилия берутся из твоего профиля Telegram автоматически.\n\n"
        "Основные кнопки внизу:\n"
        "📅 На сегодня / 📅 На завтра / 📅 На неделю\n"
        "👀 Расписание другого класса — посмотреть чужой класс\n"
        "🔁 Сменить класс — выбрать свой заново"
    )

@dp.message(Command("profile"))
async def cmd_profile(message: Message) -> None:
    chat_id = message.chat.id
    settings = user_settings.setdefault(chat_id, {})

    # Имя/фамилия теперь берутся из Telegram автоматически
    first_name = settings.get("first_name") or (message.from_user.first_name or "")
    last_name = settings.get("last_name") or (message.from_user.last_name or "")

    if first_name:
        settings["first_name"] = first_name
    if last_name:
        settings["last_name"] = last_name
    save_state()

    parallel = settings.get("parallel")
    variant = settings.get("variant")
    other_parallel = settings.get("other_parallel")
    other_variant = settings.get("other_variant")

    lines = ["<b>Твой профиль</b>"]

    if first_name:
        lines.append(f"Имя: {first_name}")
    if last_name:
        lines.append(f"Фамилия: {last_name}")
    if not first_name and not last_name:
        lines.append("Имя и фамилия не указаны (берутся из профиля Telegram).")

    if parallel and variant:
        lines.append(f"Основной класс: <b>{parallel} {variant}</b>")
    else:
        lines.append("Основной класс ещё не выбран.")

    if other_parallel and other_variant:
        lines.append(
            "Последний выбранный другой класс: "
            f"<b>{other_parallel} {other_variant}</b>"
        )

    lines.append(
        "\nКоманды:\n"
        "• /start — выбрать класс заново"
    )

    await message.answer("\n".join(lines))

# Админские команды

@dp.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда только для админов.")
        return

    await message.answer(
        "<b>Админ-команды:</b>\n"
        "/reload_schedule — сброс кэша расписания (CSV)\n"
        "/broadcast текст — разослать сообщение всем пользователям"
    )


@dp.message(Command("reload_schedule"))
async def cmd_reload_schedule(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда только для админов.")
        return

    reset_cache()
    await message.answer("Кэш расписания сброшен.")


@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("Эта команда только для админов.")
        return

    _, _, text = message.text.partition(" ")
    text = text.strip()
    if not text:
        await message.answer("Нужно указать текст рассылки: /broadcast твой текст")
        return

    if not known_users:
        await message.answer("Пока что нет пользователей для рассылки.")
        return

    sent = 0
    for user_id in list(known_users):
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except Exception as e:
            logger.warning("Не удалось отправить сообщение %s: %s", user_id, e)

    await message.answer(f"Рассылка завершена, отправлено {sent} пользователям.")


# Выбор своего класса FSM

@dp.message(UserStates.choosing_my_class, F.text.in_(PARALLELS))
async def handle_my_class_choice(message: Message, state: FSMContext) -> None:
    # Пользователь выбирает свой класс (цифру).
    chat_id = message.chat.id
    known_users.add(chat_id)

    is_reg, settings = await _ensure_registered(message, state)
    if not is_reg:
        return

    class_number = message.text.strip()

    if class_number not in CLASS_VARIANTS_BY_PARALLEL:
        await message.answer(
            f"Для класса {class_number} пока нет настроенного расписания."
        )
        return

    settings["parallel"] = class_number
    save_state()

    await state.set_state(UserStates.choosing_my_variant)

    await message.answer(
        f"Ок, класс {class_number}.\n"
        f"Теперь выбери <b>ПАРАЛЛЕЛЬ / профиль</b>:",
        reply_markup=make_parallel_keyboard(class_number),
    )


@dp.message(UserStates.choosing_my_class)
async def handle_my_class_invalid(message: Message, state: FSMContext) -> None:
    # Любой другой текст при выборе класса.
    await message.answer(
        "Пожалуйста, выбери класс с помощью кнопок ниже (5, 6, 7, ...).",
        reply_markup=make_class_keyboard(),
    )


@dp.message(UserStates.choosing_my_variant, F.text.in_(ALL_VARIANTS))
async def handle_my_variant_choice(message: Message, state: FSMContext) -> None:
    # Пользователь выбирает свою параллель/профиль.
    chat_id = message.chat.id
    settings = user_settings.setdefault(chat_id, {})
    variant = message.text.strip()
    parallel = settings.get("parallel")

    if not parallel:
        await state.set_state(UserStates.choosing_my_class)
        await message.answer(
            "Не понял, к какому классу относится этот вариант.\n"
            "Давай выберем класс ещё раз:",
            reply_markup=make_class_keyboard(),
        )
        return

    if variant not in CLASS_VARIANTS_BY_PARALLEL.get(parallel, []):
        await message.answer(
            f"В классе {parallel} нет параллели/профиля «{variant}».\n"
            "Выбери один из вариантов на клавиатуре."
        )
        return

    settings["variant"] = variant
    save_state()

    await state.set_state(UserStates.idle)

    has_other = "other_parallel" in settings and "other_variant" in settings

    await message.answer(
        f"Твой класс сохранён: <b>{parallel} {variant}</b>.\n"
        f"Теперь можешь сам выбрать:\n"
        f"— посмотреть расписание <b>на сегодня</b>,\n"
        f"— <b>на завтра</b>,\n"
        f"— или <b>на неделю</b> с помощью кнопок ниже.",
        reply_markup=make_main_menu(has_other=has_other),
    )


@dp.message(UserStates.choosing_my_variant)
async def handle_my_variant_invalid(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Пожалуйста, выбери параллель/профиль с помощью кнопок.",
    )


# Выбор чужого класса FSM

@dp.message(F.text == "👀 Расписание другого класса")
async def start_other_class_selection(message: Message, state: FSMContext) -> None:
    # Кнопка: выбор другого класса для разового просмотра.
    is_reg, _ = await _ensure_registered(message, state)
    if not is_reg:
        return

    chat_id = message.chat.id
    known_users.add(chat_id)

    await state.set_state(UserStates.choosing_other_class)
    await message.answer(
        "Выбери <b>КЛАСС</b> (цифру), расписание которого хочешь посмотреть:",
        reply_markup=make_class_keyboard(),
    )


@dp.message(UserStates.choosing_other_class, F.text.in_(PARALLELS))
async def handle_other_class_choice(message: Message, state: FSMContext) -> None:
    # Выбираем КЛАСС для чужого расписания.
    chat_id = message.chat.id
    class_number = message.text.strip()
    settings = user_settings.setdefault(chat_id, {})

    has_my_class = "parallel" in settings and "variant" in settings

    if class_number not in CLASS_VARIANTS_BY_PARALLEL:
        if has_my_class:
            await message.answer(
                f"Для класса {class_number} пока нет настроенного расписания.",
                reply_markup=make_return_to_my_schedule_keyboard(),
            )
        else:
            await message.answer(
                f"Для класса {class_number} пока нет настроенного расписания."
            )
        return

    settings["other_parallel"] = class_number
    save_state()

    await state.set_state(UserStates.choosing_other_variant)

    await message.answer(
        f"Класс {class_number}.\n"
        f"Теперь выбери <b>ПАРАЛЛЕЛЬ / профиль</b> для чужого расписания:",
        reply_markup=make_parallel_keyboard(class_number),
    )


@dp.message(UserStates.choosing_other_class)
async def handle_other_class_invalid(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Пожалуйста, выбери класс для просмотра расписания с помощью кнопок.",
        reply_markup=make_class_keyboard(),
    )


@dp.message(UserStates.choosing_other_variant, F.text.in_(ALL_VARIANTS))
async def handle_other_variant_choice(message: Message, state: FSMContext) -> None:
    # Выбираем параллель, профиль для чужого класса.
    chat_id = message.chat.id
    settings = user_settings.setdefault(chat_id, {})
    variant = message.text.strip()
    other_parallel = settings.get("other_parallel")

    has_my_class = "parallel" in settings and "variant" in settings

    if not other_parallel:
        await state.set_state(UserStates.idle)
        await message.answer(
            "Потерялся номер класса для чужого расписания.\n"
            "Попробуй ещё раз: нажми «👀 Расписание другого класса»."
        )
        return

    if variant not in CLASS_VARIANTS_BY_PARALLEL.get(other_parallel, []):
        await message.answer(
            f"В классе {other_parallel} нет параллели/профиля «{variant}».",
            )
        return

    settings["other_variant"] = variant
    save_state()

    await state.set_state(UserStates.idle)

    schedule, error = await get_class_schedule(other_parallel, variant)
    if schedule is None:
        if has_my_class:
            await message.answer(
                error or "Не удалось получить расписание.",
                reply_markup=make_return_to_my_schedule_keyboard(),
            )
        else:
            await message.answer(error or "Не удалось получить расписание.")
        return

    text = render_full_schedule(schedule)
    await send_long_text(message, text)

    await message.answer(
        f"Ты смотришь расписание класса <b>{other_parallel} {variant}</b>.\n"
        f"Теперь у тебя есть кнопки для расписания своего и выбранного класса.",
        reply_markup=make_main_menu(has_other=True),
    )


@dp.message(UserStates.choosing_other_variant)
async def handle_other_variant_invalid(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Пожалуйста, выбери параллель/профиль этого класса с помощью кнопок.",
    )

@dp.message(F.text == "↩️ Вернуться к своему расписанию")
async def back_to_my_schedule(message: Message, state: FSMContext) -> None:
    # Возврат в меню со своим классом.
    chat_id = message.chat.id
    settings = user_settings.get(chat_id, {})

    parallel = settings.get("parallel")
    variant = settings.get("variant")

    if not parallel or not variant:
        await state.set_state(UserStates.choosing_my_class)
        await message.answer(
            "Сначала выбери свой класс.\n"
            "Выбери <b>КЛАСС</b> (цифру):",
            reply_markup=make_class_keyboard(),
        )
        return

    await state.set_state(UserStates.idle)
    has_other = "other_parallel" in settings and "other_variant" in settings

    await message.answer(
        f"Ок, вернулись к твоему классу: <b>{parallel} {variant}</b>.\n"
        f"Можешь открыть расписание на сегодня/завтра/неделю или выбрать другой класс.",
        reply_markup=make_main_menu(has_other=has_other),
    )

@dp.message(F.text == "📅 На неделю")
async def send_my_week_schedule(message: Message, state: FSMContext) -> None:
    parallel, variant, settings = await _ensure_my_class(message, state)
    if not parallel or not variant:
        return

    schedule, error = await get_class_schedule(parallel, variant)
    if schedule is None:
        await message.answer(error or "Не удалось получить расписание.")
        return

    text = render_full_schedule(schedule)
    await send_long_text(message, text)


@dp.message(F.text == "📅 На сегодня")
async def send_my_today_schedule(message: Message, state: FSMContext) -> None:
    parallel, variant, settings = await _ensure_my_class(message, state)
    if not parallel or not variant:
        return

    schedule, error = await get_class_schedule(parallel, variant)
    if schedule is None:
        await message.answer(error or "Не удалось получить расписание.")
        return

    day_name = get_today_day_name()
    if day_name is None:
        phrase = get_free_time_text()
        await message.answer(
            f"Сегодня уроков нет (выходной). {phrase}\n\n"
            f"Вот расписание на неделю:"
        )
        text = render_full_schedule(schedule)
        await send_long_text(message, text)
        return

    text = render_day_schedule(schedule, day_name)
    await send_long_text(message, text)


@dp.message(F.text == "📅 На завтра")
async def send_my_tomorrow_schedule(message: Message, state: FSMContext) -> None:
    parallel, variant, settings = await _ensure_my_class(message, state)
    if not parallel or not variant:
        return

    schedule, error = await get_class_schedule(parallel, variant)
    if schedule is None:
        await message.answer(error or "Не удалось получить расписание.")
        return

    day_name = get_tomorrow_day_name()
    if day_name is None:
        phrase = get_free_time_text()
        await message.answer(
            f"Завтра уроков нет (выходной). {phrase}\n\n"
            f"Вот расписание на неделю:"
        )
        text = render_full_schedule(schedule)
        await send_long_text(message, text)
        return

    text = render_day_schedule(schedule, day_name)
    await send_long_text(message, text)

@dp.message(F.text == "📅 Расписание выбранного класса")
async def send_other_selected_schedule(message: Message, state: FSMContext) -> None:
    is_reg, _ = await _ensure_registered(message, state)
    if not is_reg:
        return

    chat_id = message.chat.id
    settings = user_settings.get(chat_id, {})
    other_parallel = settings.get("other_parallel")
    other_variant = settings.get("other_variant")

    if not other_parallel or not other_variant:
        await message.answer(
            "Ты ещё не выбирал другой класс.\n"
            "Нажми «👀 Расписание другого класса», чтобы выбрать.",
            reply_markup=make_main_menu(has_other=False),
        )
        return

    schedule, error = await get_class_schedule(other_parallel, other_variant)
    if schedule is None:
        await message.answer(error or "Не удалось получить расписание.")
        return

    text = render_full_schedule(schedule)
    await send_long_text(message, text)

@dp.message(F.text == "🔁 Сменить класс")
async def change_my_class(message: Message, state: FSMContext) -> None:
    # Кнопка: полностью переиграть выбор своего класса.
    is_reg, settings = await _ensure_registered(message, state)
    if not is_reg:
        return

    chat_id = message.chat.id
    settings = user_settings.setdefault(chat_id, {})

    settings.pop("parallel", None)
    settings.pop("variant", None)
    save_state()

    await state.set_state(UserStates.choosing_my_class)

    await message.answer(
        "Давай выберем твой класс заново.\n"
        "Сначала выбери <b>КЛАСС</b> (цифру):",
        reply_markup=make_class_keyboard(),
    )


# Общий fallback-обработчик

@dp.message()
async def fallback_handler(message: Message, state: FSMContext) -> None:
    is_reg, _ = await _ensure_registered(message, state)
    if not is_reg:
        return

    await message.answer(
        "Я не понял это сообщение.\n"
        "Используй, пожалуйста, кнопки под строкой ввода или команду /help."
    )
