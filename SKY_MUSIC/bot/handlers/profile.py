from __future__ import annotations

from typing import Any
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from bot.database.queries import get_quota_status
from bot.utils.permissions import ROLE_LABELS, Role

router = Router(name="profile")


def _format_profile_text(user: dict[str, Any], quota: dict[str, Any]) -> str:
    user_id = int(user["user_id"])
    role: Role = user["effective_role"]
    username = f"@{user['username']}" if user.get("username") else "не указан"
    reg_date = str(user.get("registered_at") or "")[:19].replace("T", " ")
    total_proc = int(user.get("total_processed") or 0)

    if quota["unlimited"]:
        quota_str = "♾️ БЕЗ ОГРАНИЧЕНИЙ"
    else:
        quota_str = f"{quota['remaining']}/{quota['total']} (использовано сегодня: {quota['used']})"

    return (
        "👤 <b>Мой профиль — SKY MUSIC</b>\n\n"
        f"• <b>ID:</b> <code>{user_id}</code>\n"
        f"• <b>Username:</b> {username}\n"
        f"• <b>Роль:</b> <b>{ROLE_LABELS[role]}</b>\n"
        f"• <b>Лимит сегодня:</b> <b>{quota_str}</b>\n"
        f"• <b>Всего обработок:</b> <b>{total_proc}</b>\n"
        f"• <b>Регистрация:</b> <code>{reg_date}</code>"
    )


@router.message(Command("profile"))
async def cmd_profile(message: Message, db_user: dict[str, Any]) -> None:
    quota = await get_quota_status(db_user)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")]]
    )
    await message.answer(_format_profile_text(db_user, quota), reply_markup=kb)


@router.callback_query(F.data == "menu:profile")
async def cb_profile(callback: CallbackQuery, db_user: dict[str, Any]) -> None:
    quota = await get_quota_status(db_user)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:main")]]
    )
    if callback.message:
        try:
            await callback.message.edit_text(_format_profile_text(db_user, quota), reply_markup=kb)
        except Exception:
            await callback.message.answer(_format_profile_text(db_user, quota), reply_markup=kb)
    await callback.answer()
