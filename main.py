import asyncio

from loader import bot, dp, logger
import handlers  # noqa: F401 # зарегистрировать хендлеры


async def main() -> None:
    logger.info("Бот запускается...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
