from __future__ import annotations

from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User, Message, CallbackQuery
from bot.database.queries import upsert_user, get_setting
from bot.utils.permissions import is_developer


class AuthAndMaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: User | None = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        reg_open = (await get_setting("registration_open", "1")) == "1"
        maintenance = (await get_setting("maintenance_mode", "0")) == "1"

        user_record, _ = await upsert_user(
            user_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
            allow_registration=reg_open,
        )

        if user_record is None:
            text = "🔒 <b>SKY MUSIC</b>\n\nРегистрация новых пользователей временно приостановлена."
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer("Регистрация временно закрыта.", show_alert=True)
            return None

        if user_record.get("is_banned") and not is_developer(tg_user.id, user_record.get("effective_role")):
            reason = user_record.get("ban_reason") or "Нарушение правил использования"
            text = f"🚫 <b>Доступ ограничен</b>\n\nВаш аккаунт заблокирован в <b>SKY MUSIC</b>.\nПричина: <code>{reason}</code>"
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer("Ваш аккаунт заблокирован.", show_alert=True)
            return None

        if maintenance and not is_developer(tg_user.id, user_record.get("effective_role")):
            text = (
                "🛠️ <b>Техническое обслуживание</b>\n\n"
                "Студия <b>SKY MUSIC</b> временно обновляет аудиомодули. Попробуйте позже."
            )
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer("Идёт техническое обслуживание.", show_alert=True)
            return None

        data["db_user"] = user_record
        return await handler(event, data)
