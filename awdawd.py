Сделаем отдельный «тормоз» именно для /broadcast, чтобы админ случайно не замочил рассылкой бота 😄

Сделаем так:

у каждого админа будет кд (cooldown) на рассылку, например 1 раз в 30 секунд;

если админ дергает /broadcast чаще — бот скажет, сколько ещё ждать;

проверим длину сообщения, чтобы не улететь за лимит Телеграма.

Ниже — точечные правки, только handlers.py.

1. Добавляем импорты и константы

Вверху handlers.py добавь:

1.1. Импорт time и (по желанию) типов
import logging
import time  # <-- добавить

from aiogram import F
...


Если хочешь типизацию, можешь ещё добавить:

from typing import Dict


но это не обязательно.

1.2. Дополнить импорт из config

Сейчас у тебя так:

from config import ALL_VARIANTS, CLASS_VARIANTS_BY_PARALLEL, PARALLELS


Замени на:

from config import ALL_VARIANTS, CLASS_VARIANTS_BY_PARALLEL, PARALLELS, MAX_MESSAGE_LENGTH


(чтобы использовать тот же лимит длины, что и в send_long_text).

1.3. Добавить глобальные переменные под /broadcast

Сразу после логгера:

logger = logging.getLogger(__name__)

# Ограничение по рассылке для админов
BROADCAST_COOLDOWN_SECONDS = 30.0  # кд между /broadcast для одного админа
_last_broadcast_by_admin = {}      # user_id -> time.monotonic()

2. Меняем хендлер /broadcast

Найди в handlers.py текущую функцию:

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


И замени её целиком на эту:

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message) -> None:
    """Рассылка сообщения всем пользователям с защитой от спама."""
    user = message.from_user
    if user is None or not is_admin(user.id):
        await message.answer("Эта команда только для админов.")
        return

    # Текст после команды
    _, _, text = message.text.partition(" ")
    text = text.strip()
    if not text:
        await message.answer("Нужно указать текст рассылки: /broadcast твой текст")
        return

    # Проверка длины (чтобы не сломаться об лимит Телеграма)
    if len(text) > MAX_MESSAGE_LENGTH:
        await message.answer(
            f"Слишком длинное сообщение для рассылки "
            f"({len(text)} символов). Лимит — {MAX_MESSAGE_LENGTH}."
        )
        return

    # Проверка кд на /broadcast для конкретного админа
    now = time.monotonic()
    last_time = _last_broadcast_by_admin.get(user.id, 0.0)
    delta = now - last_time

    if delta < BROADCAST_COOLDOWN_SECONDS:
        wait_sec = int(BROADCAST_COOLDOWN_SECONDS - delta) + 1
        await message.answer(
            f"Слишком часто используешь /broadcast.\n"
            f"Подожди ещё {wait_sec} сек."
        )
        return

    if not known_users:
        await message.answer("Пока что нет пользователей для рассылки.")
        return

    # Фиксируем время рассылки
    _last_broadcast_by_admin[user.id] = now

    # Делаем рассылку
    sent = 0
    errors = 0
    for user_id in list(known_users):
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except Exception as e:
            errors += 1
            logger.warning("Не удалось отправить сообщение %s: %s", user_id, e)

    await message.answer(
        f"Рассылка завершена.\n"
        f"Отправлено: {sent} пользователям."
        + (f"\nОшибок отправки: {errors}." if errors else "")
    )