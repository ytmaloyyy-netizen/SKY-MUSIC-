from __future__ import annotations

from typing import Any
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from bot.database.queries import get_quota_status, get_user_files
from bot.handlers.start import build_welcome_text
from bot.keyboards.main import main_menu_keyboard, back_to_main_keyboard
from bot.utils.permissions import Role, ROLE_LABELS, is_admin_or_above

router = Router(name="menu")


async def _safe_edit(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=reply_markup)
        except Exception:
            await callback.message.answer(text, reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(F.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery, db_user: dict[str, Any]) -> None:
    quota = await get_quota_status(db_user)
    text = build_welcome_text(db_user, quota)
    kb = main_menu_keyboard(int(db_user["user_id"]), db_user["effective_role"])
    await _safe_edit(callback, text, kb)


@router.callback_query(F.data == "menu:premium")
async def cb_premium(callback: CallbackQuery) -> None:
    text = (
        "⭐ <b>Тариф 🌟 PREMIUM</b>\n\n"
        "• <b>♾️ Бесконечные обработки</b> (в рамках серверных и Telegram-лимитов)\n"
        "• <b>⚡ Приоритетная очередь</b> задач\n"
        "• <b>🎛️ Расширенные настройки</b> скорости, тональности и эффектов\n"
        "• <b>✏️ Расширенный редактор аудио</b> и тегов\n\n"
        "ℹ️ <i>Режимы 8D / 16D / 32D не входят в тариф PREMIUM и доступны только администраторам.</i>\n"
        "Для активации или продления подписки обратитесь к администратору или разработчику студии."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Мой профиль", callback_data="menu:profile")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:main")],
        ]
    )
    await _safe_edit(callback, text, kb)


@router.callback_query(F.data == "menu:files")
async def cb_my_files(callback: CallbackQuery, db_user: dict[str, Any]) -> None:
    user_id = int(db_user["user_id"])
    files = await get_user_files(user_id, limit=8)
    if not files:
        text = (
            "📂 <b>Мои файлы</b>\n\n"
            "Вы пока не загружали аудиофайлы в <b>SKY MUSIC</b>.\n"
            "Отправьте аудиофайл, голосовое сообщение, видео или документ в нужный раздел обработки."
        )
    else:
        lines = ["📂 <b>Мои последние файлы</b>\n"]
        for item in files:
            fname = item.get("file_name") or item.get("file_unique_id")
            size_mb = (int(item.get("file_size") or 0)) / (1024 * 1024)
            lines.append(f"• <code>{fname}</code> — <b>{size_mb:.2f} МБ</b>")
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:main")]]
    )
    await _safe_edit(callback, text, kb)


@router.callback_query(F.data == "menu:help")
async def cb_help(callback: CallbackQuery) -> None:
    text = (
        "❓ <b>Помощь по студии SKY MUSIC</b>\n\n"
        "1. Выберите раздел в главном меню (например, <b>🎵 Обработка музыки</b>).\n"
        "2. Отправьте аудиофайл, голосовое сообщение, видео с аудиодорожкой или аудиодокумент.\n"
        "3. Выберите пресет или точные параметры и дождитесь готового файла.\n\n"
        "<b>Основные команды:</b>\n"
        "• <code>/start</code> — главное меню и статус лимитов\n"
        "• <code>/myid</code> — узнать свой Telegram ID\n"
        "• <code>/profile</code> — подробный профиль и тариф"
    )
    await _safe_edit(callback, text, back_to_main_keyboard())


@router.callback_query(F.data == "menu:admin_tools")
async def cb_admin_tools(callback: CallbackQuery, db_user: dict[str, Any]) -> None:
    user_id = int(db_user["user_id"])
    role: Role = db_user["effective_role"]
    if not is_admin_or_above(user_id, role):
        await callback.answer("⛔ Недостаточно прав.", show_alert=True)
        return

    text = (
        f"🛡️ <b>Админ-инструменты</b>\n\n"
        f"Ваша роль: <b>{ROLE_LABELS[role]}</b>\n"
        "• Доступ к пространственному звуку <b>8D / 16D / 32D</b>\n"
        "• Безлимитная обработка аудио в рамках серверных ограничений\n"
        "• Управление пользователями в рамках полномочий"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌌 Открыть пространственный звук", callback_data="menu:spatial")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:main")],
        ]
    )
    await _safe_edit(callback, text, kb)
