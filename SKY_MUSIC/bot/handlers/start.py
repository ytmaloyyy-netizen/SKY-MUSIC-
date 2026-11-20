from __future__ import annotations

from typing import Any
from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from config import config
from bot.database.queries import get_quota_status
from bot.keyboards.main import main_menu_keyboard
from bot.utils.permissions import ROLE_LABELS, Role, is_developer

router = Router(name="start")


def format_quota_line(quota: dict[str, Any], role: Role) -> str:
    if quota["unlimited"]:
        return "Лимит: <b>♾️ БЕЗ ОГРАНИЧЕНИЙ</b>"
    total = quota["total"]
    remaining = quota["remaining"]
    if role == Role.DEFAULT and total == 5 and quota["bonus"] == 0:
        return f"Лимит: <b>{remaining}/5 обработок в день</b>"
    return f"Лимит: <b>{remaining}/{total} обработок на сегодня</b>"


def build_welcome_text(user: dict[str, Any], quota: dict[str, Any]) -> str:
    user_id = int(user["user_id"])
    role: Role = user["effective_role"]
    role_badge = ROLE_LABELS.get(role, str(role))
    quota_line = format_quota_line(quota, role)

    dev_warning = ""
    if is_developer(user_id, role) and not config.is_developer_configured:
        dev_warning = (
            "\n\n⚠️ <b>Внимание:</b> <code>DEVELOPER_ID</code> не задан в <code>.env</code>! "
            "Укажите ваш Telegram ID в конфигурации перед продакшн-запуском."
        )

    return (
        "🎧 <b>SKY MUSIC</b>\n\n"
        "Твоя персональная музыкальная студия.\n"
        "Преобразуй обычное аудио в совершенно новое звучание!\n\n"
        f"Роль: <b>{role_badge}</b>\n"
        f"{quota_line}"
        f"{dev_warning}"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: dict[str, Any]) -> None:
    quota = await get_quota_status(db_user)
    text = build_welcome_text(db_user, quota)
    kb = main_menu_keyboard(int(db_user["user_id"]), db_user["effective_role"])
    await message.answer(text, reply_markup=kb)


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    tg_id = message.from_user.id if message.from_user else 0
    await message.answer(
        f"🆔 <b>Ваш Telegram ID:</b> <code>{tg_id}</code>\n\n"
        "Для настройки роли разработчика укажите его в <code>.env</code>:\n"
        f"<code>DEVELOPER_ID={tg_id}</code>"
    )
