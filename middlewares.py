import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

from utils import is_admin


class AntiFloodMiddleware(BaseMiddleware):

    def __init__(self, interval: float = 1.0, max_messages: int = 5, block_time: float = 10.0):
        self.interval = interval
        self.max_messages = max_messages
        self.block_time = block_time
        self.users: Dict[int, Dict[str, Any]] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        if event.from_user is None:
            return await handler(event, data)

        user_id = event.from_user.id

        # Админов не ограничиваем
        if is_admin(user_id):
            return await handler(event, data)

        now = time.monotonic()
        info = self.users.get(user_id)
        if info is None:
            info = {
                "last_time": now,
                "count": 0,
                "blocked_until": 0.0,
                "notified": False,
            }
            self.users[user_id] = info

        blocked_until = float(info.get("blocked_until", 0.0))
        if now < blocked_until:
            return

        last_time = float(info.get("last_time", 0.0))
        count = int(info.get("count", 0))

        if now - last_time > self.interval:
            count = 0
            info["notified"] = False

        count += 1
        info["last_time"] = now
        info["count"] = count

        if count > self.max_messages:
            info["blocked_until"] = now + self.block_time
            if not info.get("notified", False):
                try:
                    await event.answer("Слишком много сообщений. Подожди немного и попробуй снова.")
                except Exception:
                    pass
                info["notified"] = True
            return  # дальше хендлеры не вызываем

        return await handler(event, data)
