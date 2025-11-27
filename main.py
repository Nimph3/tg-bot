import asyncio

from loader import bot, dp, logger
import handlers  # noqa: F401 # зарегистрировать хендлеры
from middlewares import AntiFloodMiddleware

async def main() -> None:
    logger.info("Бот запускается...")

    dp.message.outer_middleware(
        AntiFloodMiddleware(
            interval=1.0,
            max_messages=5,
            block_time=10.0,
        )
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
