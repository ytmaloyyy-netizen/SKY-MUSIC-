from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, CallbackQuery, Message


class AntiDoubleClickMiddleware(BaseMiddleware):
    """Защищает от повторных нажатий/запусков одной задачи пользователем."""

    def __init__(self) -> None:
        self._active_locks: dict[int, asyncio.Lock] = {}

    def _get_lock(self, user_id: int) -> asyncio.Lock:
        if user_id not in self._active_locks:
            self._active_locks[user_id] = asyncio.Lock()
        return self._active_locks[user_id]

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        # Блокируем параллельный запуск тяжёлых обработок одним пользователем
        is_heavy_callback = isinstance(event, CallbackQuery) and bool(
            event.data and event.data.startswith(("run_", "spatial_", "vocal_"))
        )
        if not is_heavy_callback:
            return await handler(event, data)

        lock = self._get_lock(tg_user.id)
        if lock.locked():
            if isinstance(event, CallbackQuery):
                await event.answer("⏳ Предыдущая операция уже выполняется, дождитесь завершения.", show_alert=False)
            return None

        async with lock:
            return await handler(event, data)
