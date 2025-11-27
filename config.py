import os

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

TOKEN_BOT = os.getenv("TOKEN_BOT")

if not TOKEN_BOT:
    raise RuntimeError(
        "Не задан токен бота. Установи переменную окружения TOKEN_BOT "
        "или добавь её в .env."
    )

SHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "17iHtFw9e_IsKDDksdv4fAbIuOuLkLPxVeYlyi6Db_lY/export?format=csv&gid=1405588358"
)

PARALLELS = ["5", "6", "7", "8", "9", "10", "11"]

CLASS_VARIANTS_BY_PARALLEL = {
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
    {variant for variants in CLASS_VARIANTS_BY_PARALLEL.values() for variant in variants}
)

MAX_MESSAGE_LENGTH = 4000

DAY_NAMES = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]

SCHEDULE_CACHE_TTL = 300

ADMIN_IDS = [
    123456789,  # Поменять на id админа
]
