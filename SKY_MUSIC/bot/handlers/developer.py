from __future__ import annotations

import html
import logging
from datetime import datetime
from typing import Any
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import config
from bot.database.database import db
from bot.database.queries import (
    get_user,
    get_stats,
    get_setting,
    set_setting,
    assign_role,
    log_admin_action,
    sync_daily_quota,
)
from bot.keyboards.developer import (
    developer_panel_keyboard,
    dev_roles_keyboard,
    dev_limits_keyboard,
    dev_bans_keyboard,
    dev_settings_keyboard,
    dev_broadcast_audience_keyboard,
    dev_broadcast_confirm_keyboard,
)
from bot.utils.permissions import Role, is_developer

logger = logging.getLogger("sky_music.developer")
router = Router(name="developer")

DENIED_TEXT = "⛔ Доступ запрещён: Developer Panel доступна только владельцу системы (DEVELOPER_ID)."


class DevStates(StatesGroup):
    waiting_user_lookup = State()
    waiting_role_input = State()
    waiting_limit_input = State()
    waiting_ban_input = State()
    waiting_broadcast_text = State()


def _authorized_dev(user_id: int | None, db_user: dict[str, Any] | None = None) -> bool:
    if not user_id:
        return False
    role = db_user.get("effective_role") if db_user else None
    return is_developer(user_id, role)


async def _edit_or_send(target: Message | CallbackQuery, text: str, kb: InlineKeyboardMarkup) -> None:
    if isinstance(target, CallbackQuery):
        if target.message:
            try:
                await target.message.edit_text(text, reply_markup=kb)
            except Exception:
                await target.message.answer(text, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)


@router.message(Command("dev"))
async def cmd_dev(message: Message, db_user: dict[str, Any]) -> None:
    uid = message.from_user.id if message.from_user else 0
    if not _authorized_dev(uid, db_user):
        await message.answer(DENIED_TEXT)
        return

    extra_note = ""
    if not config.is_developer_configured:
        extra_note = "\n\n⚠️ <code>DEVELOPER_ID</code> не задан в <code>.env</code>! Укажите ваш ID для постоянной защиты."

    text = (
        "👑 <b>DEVELOPER PANEL — SKY MUSIC</b>\n\n"
        f"ID владельца: <code>{uid}</code>\n"
        "Полный контроль над ролями, лимитами, блокировками, статистикой и рассылкой."
        f"{extra_note}"
    )
    await message.answer(text, reply_markup=developer_panel_keyboard())


@router.callback_query(F.data == "dev:panel")
async def cb_dev_panel(callback: CallbackQuery, state: FSMContext, db_user: dict[str, Any]) -> None:
    uid = callback.from_user.id if callback.from_user else 0
    if not _authorized_dev(uid, db_user):
        await callback.answer(DENIED_TEXT, show_alert=True)
        return
    await state.set_state(None)
    text = (
        "👑 <b>DEVELOPER PANEL — SKY MUSIC</b>\n\n"
        f"ID владельца: <code>{uid}</code>\n"
        "Выберите раздел управления:"
    )
    await _edit_or_send(callback, text, developer_panel_keyboard())


async def _render_stats(target: Message | CallbackQuery) -> None:
    st = await get_stats()
    text = (
        "📊 <b>Полная статистика — SKY MUSIC</b>\n\n"
        f"• <b>Всего пользователей:</b> <code>{st['total_users']}</code>\n"
        f"• <b>Активных сегодня:</b> <code>{st['active_today']}</code>\n"
        f"• <b>Новых сегодня:</b> <code>{st['new_today']}</code>\n"
        f"• <b>Всего обработок:</b> <code>{st['total_processed']}</code>\n"
        f"• <b>Slowed / Ultra Slowed:</b> <code>{st['slowed_count']}</code>\n"
        f"• <b>Speed Up / Nightcore:</b> <code>{st['speed_up_count']}</code>\n"
        f"• <b>Пространственные (8D/16D/32D):</b> <code>{st['spatial_count']}</code>\n"
        f"• <b>Ошибок обработки:</b> <code>{st['errors_count']}</code>\n"
        f"• <b>Пользователей PREMIUM:</b> <code>{st['premium_count']}</code>\n"
        f"• <b>Администраторов ADMIN:</b> <code>{st['admin_count']}</code>"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="dev:stats")],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="dev:panel"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
            ],
        ]
    )
    await _edit_or_send(target, text, kb)


@router.message(Command("stats"))
async def cmd_stats(message: Message, db_user: dict[str, Any]) -> None:
    uid = message.from_user.id if message.from_user else 0
    if not _authorized_dev(uid, db_user):
        await message.answer(DENIED_TEXT)
        return
    await _render_stats(message)


@router.callback_query(F.data == "dev:stats")
async def cb_stats(callback: CallbackQuery, db_user: dict[str, Any]) -> None:
    uid = callback.from_user.id if callback.from_user else 0
    if not _authorized_dev(uid, db_user):
        await callback.answer(DENIED_TEXT, show_alert=True)
        return
    await _render_stats(callback)


async def _render_users_list(target: Message | CallbackQuery) -> None:
    cur = await db.conn.execute(
        "SELECT user_id, username, role, is_banned, total_processed FROM users ORDER BY last_active_at DESC LIMIT 12"
    )
    rows = [dict(r) for r in await cur.fetchall()]
    lines = ["👥 <b>Последние пользователи (до 12):</b>\n"]
    for r in rows:
        uname = f"@{html.escape(str(r['username']))}" if r.get("username") else "без username"
        ban_flag = "🚫" if r.get("is_banned") else "✅"
        lines.append(
            f"{ban_flag} <code>{r['user_id']}</code> | {uname} | <b>{r['role']}</b> | обр.: <code>{r['total_processed']}</code>"
        )
    lines.append("\nДля поиска профиля по Telegram ID отправьте числовой ID:")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="dev:panel")],
        ]
    )
    await _edit_or_send(target, "\n".join(lines), kb)


@router.message(Command("users"))
async def cmd_users(message: Message, state: FSMContext, db_user: dict[str, Any]) -> None:
    uid = message.from_user.id if message.from_user else 0
    if not _authorized_dev(uid, db_user):
        await message.answer(DENIED_TEXT)
        return
    await state.set_state(DevStates.waiting_user_lookup)
    await _render_users_list(message)


@router.callback_query(F.data == "dev:users")
async def cb_dev_users(callback: CallbackQuery, state: FSMContext, db_user: dict[str, Any]) -> None:
    uid = callback.from_user.id if callback.from_user else 0
    if not _authorized_dev(uid, db_user):
        await callback.answer(DENIED_TEXT, show_alert=True)
        return
    await state.set_state(DevStates.waiting_user_lookup)
    await _render_users_list(callback)


@router.message(DevStates.waiting_user_lookup)
async def handle_user_lookup(message: Message, state: FSMContext, db_user: dict[str, Any]) -> None:
    uid = message.from_user.id if message.from_user else 0
    if not _authorized_dev(uid, db_user):
        await message.answer(DENIED_TEXT)
        return

    raw = (message.text or "").strip().lstrip("@")
    target_user: dict[str, Any] | None = None
    if raw.isdigit():
        target_user = await get_user(int(raw))
    else:
        cur = await db.conn.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (raw,))
        row = await cur.fetchone()
        if row:
            target_user = dict(row)
            from bot.utils.permissions import resolve_effective_role
            target_user["effective_role"] = resolve_effective_role(int(target_user["user_id"]), target_user.get("role"))

    await state.set_state(None)
    if not target_user:
        await message.answer("⚠️ Пользователь не найден.", reply_markup=developer_panel_keyboard())
        return

    q = await sync_daily_quota(int(target_user["user_id"]))
    hist_cur = await db.conn.execute(
        "SELECT operation_name, status, created_at FROM processing_history WHERE user_id = ? ORDER BY id DESC LIMIT 5",
        (int(target_user["user_id"]),),
    )
    hist_rows = [dict(h) for h in await hist_cur.fetchall()]
    hist_lines = [f"• {html.escape(str(h['operation_name']))} ({h['status']})" for h in hist_rows] or ["— нет записей —"]

    text = (
        "👤 <b>Карточка пользователя</b>\n\n"
        f"• <b>ID:</b> <code>{target_user['user_id']}</code>\n"
        f"• <b>Username:</b> @{html.escape(str(target_user.get('username') or '—'))}\n"
        f"• <b>Роль:</b> <b>{target_user['effective_role']}</b>\n"
        f"• <b>Статус бана:</b> <b>{'ЗАБЛОКИРОВАН' if target_user.get('is_banned') else 'Активен'}</b>\n"
        f"• <b>Всего обработок:</b> <code>{target_user['total_processed']}</code>\n"
        f"• <b>Сегодня использовано:</b> <code>{q['used_today']}</code> (бонус: <code>{q['bonus_credits']}</code>)\n"
        f"• <b>Регистрация:</b> <code>{str(target_user['registered_at'])[:19]}</code>\n\n"
        "<b>Последние операции:</b>\n" + "\n".join(hist_lines)
    )
    await message.answer(text, reply_markup=developer_panel_keyboard())


@router.callback_query(F.data == "dev:roles")
async def cb_dev_roles(callback: CallbackQuery, db_user: dict[str, Any]) -> None:
    if not _authorized_dev(callback.from_user.id, db_user):
        await callback.answer(DENIED_TEXT, show_alert=True)
        return
    text = (
        "👑 <b>Управление ролями</b>\n\n"
        "Роль <b>DEVELOPER</b> закреплена за <code>DEVELOPER_ID</code> и не может быть изменена через панель.\n"
        "Для выдачи <b>PREMIUM</b> можно указать срок в днях: <code>USER_ID ДНИ</code> (например, <code>123456789 30</code>)."
    )
    await _edit_or_send(callback, text, dev_roles_keyboard())


@router.callback_query(F.data.startswith("dev_act:role:"))
async def cb_dev_role_prompt(callback: CallbackQuery, state: FSMContext, db_user: dict[str, Any]) -> None:
    if not _authorized_dev(callback.from_user.id, db_user):
        await callback.answer(DENIED_TEXT, show_alert=True)
        return
    role_code = callback.data.split(":")[-1]
    await state.set_state(DevStates.waiting_role_input)
    await state.update_data(dev_target_role=role_code)
    if callback.message:
        await callback.message.answer(
            f"👑 Введите <code>USER_ID</code> (и при необходимости кол-во дней для PREMIUM через пробел), "
            f"чтобы назначить <b>{role_code}</b>:"
        )
    await callback.answer()


@router.message(DevStates.waiting_role_input)
async def handle_dev_role_input(message: Message, state: FSMContext, db_user: dict[str, Any]) -> None:
    uid = message.from_user.id if message.from_user else 0
    if not _authorized_dev(uid, db_user):
        await message.answer(DENIED_TEXT)
        return

    parts = (message.text or "").strip().split()
    if not parts or not parts[0].isdigit():
        await message.answer("⚠️ Введите корректный числовой <code>USER_ID</code>.")
        return

    target_id = int(parts[0])
    days = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    data = await state.get_data()
    role_code = str(data.get("dev_target_role", "DEFAULT"))
    await state.set_state(None)

    ok, msg = await assign_role(target_id, Role(role_code), actor_id=uid, premium_days=days)
    await message.answer(f"{'✅' if ok else '⛔'} {msg}", reply_markup=dev_roles_keyboard())


@router.callback_query(F.data == "dev:list_privileged")
async def cb_list_privileged(callback: CallbackQuery, db_user: dict[str, Any]) -> None:
    if not _authorized_dev(callback.from_user.id, db_user):
        await callback.answer(DENIED_TEXT, show_alert=True)
        return
    cur = await db.conn.execute("SELECT user_id, username, role FROM users WHERE role IN ('ADMIN', 'PREMIUM')")
    rows = [dict(r) for r in await cur.fetchall()]
    if not rows:
        txt = "📋 Активных ADMIN и PREMIUM пользователей пока нет."
    else:
        txt = "📋 <b>ADMIN и PREMIUM пользователи:</b>\n\n" + "\n".join(
            f"• <code>{r['user_id']}</code> (@{html.escape(str(r['username'] or '—'))}) — <b>{r['role']}</b>"
            for r in rows
        )
    await _edit_or_send(callback, txt, dev_roles_keyboard())


@router.callback_query(F.data == "dev:limits")
async def cb_dev_limits(callback: CallbackQuery, db_user: dict[str, Any]) -> None:
    if not _authorized_dev(callback.from_user.id, db_user):
        await callback.answer(DENIED_TEXT, show_alert=True)
        return
    await _edit_or_send(callback, "🎟️ <b>Управление лимитами обработок</b>", dev_limits_keyboard())


@router.callback_query(F.data.startswith("dev_act:limit:"))
async def cb_dev_limit_prompt(callback: CallbackQuery, state: FSMContext, db_user: dict[str, Any]) -> None:
    if not _authorized_dev(callback.from_user.id, db_user):
        await callback.answer(DENIED_TEXT, show_alert=True)
        return
    action = callback.data.split(":")[-1]
    await state.set_state(DevStates.waiting_limit_input)
    await state.update_data(dev_limit_action=action)
    prompts = {
        "bonus": "Введите <code>USER_ID КОЛИЧЕСТВО</code> для начисления доп. обработок на сегодня:",
        "custom": "Введите <code>USER_ID ДНЕВНОЙ_ЛИМИТ</code> для установки индивидуального лимита:",
        "reset": "Введите <code>USER_ID</code> для сброса дневного счётчика на сегодня:",
        "unlimited": "Введите <code>USER_ID 1</code> (включить безлимит) или <code>USER_ID 0</code> (выключить):",
        "default_cap": "Введите новое число суточного лимита для роли DEFAULT (например, <code>5</code>):",
    }
    if callback.message:
        await callback.message.answer(f"🎟️ {prompts.get(action, 'Введите данные:')}")
    await callback.answer()


@router.message(DevStates.waiting_limit_input)
async def handle_dev_limit_input(message: Message, state: FSMContext, db_user: dict[str, Any]) -> None:
    uid = message.from_user.id if message.from_user else 0
    if not _authorized_dev(uid, db_user):
        await message.answer(DENIED_TEXT)
        return

    data = await state.get_data()
    action = str(data.get("dev_limit_action", ""))
    parts = (message.text or "").strip().split()
    await state.set_state(None)

    if action == "default_cap":
        if not parts or not parts[0].isdigit() or int(parts[0]) < 1:
            await message.answer("⚠️ Введите положительное целое число.")
            return
        new_cap = int(parts[0])
        await set_setting("default_daily_limit", str(new_cap), actor_id=uid)
        await message.answer(f"✅ Суточный лимит DEFAULT обновлён: <b>{new_cap}</b>.", reply_markup=dev_limits_keyboard())
        return

    if not parts or not parts[0].isdigit():
        await message.answer("⚠️ Неверный формат. Укажите числовой <code>USER_ID</code>.")
        return

    target_id = int(parts[0])
    target = await get_user(target_id)
    if not target:
        await message.answer("⚠️ Пользователь не найден.", reply_markup=dev_limits_keyboard())
        return

    await sync_daily_quota(target_id)
    now_iso = datetime.now(config.tz).isoformat()

    if action == "bonus" and len(parts) >= 2 and parts[1].lstrip("-").isdigit():
        bonus = int(parts[1])
        await db.conn.execute(
            "UPDATE usage_limits SET bonus_credits = MAX(0, bonus_credits + ?), updated_at = ? WHERE user_id = ?",
            (bonus, now_iso, target_id),
        )
        await db.conn.commit()
        await log_admin_action(uid, "BONUS_LIMIT", target_id, f"bonus={bonus}")
        await message.answer(f"✅ Начислено бонусных обработок: <b>{bonus}</b> для <code>{target_id}</code>.", reply_markup=dev_limits_keyboard())
    elif action == "custom" and len(parts) >= 2 and parts[1].isdigit():
        lim = int(parts[1])
        await db.conn.execute("UPDATE users SET custom_daily_limit = ? WHERE user_id = ?", (lim, target_id))
        await db.conn.commit()
        await log_admin_action(uid, "CUSTOM_LIMIT", target_id, f"custom_limit={lim}")
        await message.answer(f"✅ Индивидуальный лимит <code>{target_id}</code> установлен: <b>{lim}</b>.", reply_markup=dev_limits_keyboard())
    elif action == "reset":
        await db.conn.execute("UPDATE usage_limits SET used_today = 0, updated_at = ? WHERE user_id = ?", (now_iso, target_id))
        await db.conn.commit()
        await log_admin_action(uid, "RESET_LIMIT", target_id, "used_today=0")
        await message.answer(f"✅ Дневной лимит пользователя <code>{target_id}</code> сброшен.", reply_markup=dev_limits_keyboard())
    elif action == "unlimited" and len(parts) >= 2 and parts[1] in {"0", "1"}:
        flag = int(parts[1])
        await db.conn.execute("UPDATE users SET unlimited_quota = ? WHERE user_id = ?", (flag, target_id))
        await db.conn.commit()
        await log_admin_action(uid, "UNLIMITED_QUOTA", target_id, f"unlimited={flag}")
        await message.answer(f"✅ Безлимитный тариф для <code>{target_id}</code>: <b>{'ВКЛ' if flag else 'ВЫКЛ'}</b>.", reply_markup=dev_limits_keyboard())
    else:
        await message.answer("⚠️ Проверьте введённые параметры.", reply_markup=dev_limits_keyboard())


@router.callback_query(F.data == "dev:bans")
async def cb_dev_bans(callback: CallbackQuery, db_user: dict[str, Any]) -> None:
    if not _authorized_dev(callback.from_user.id, db_user):
        await callback.answer(DENIED_TEXT, show_alert=True)
        return
    await _edit_or_send(callback, "🚫 <b>Блокировки и предупреждения</b>", dev_bans_keyboard())


@router.callback_query(F.data.startswith("dev_act:ban:"))
async def cb_dev_ban_prompt(callback: CallbackQuery, state: FSMContext, db_user: dict[str, Any]) -> None:
    if not _authorized_dev(callback.from_user.id, db_user):
        await callback.answer(DENIED_TEXT, show_alert=True)
        return
    action = callback.data.split(":")[-1]
    await state.set_state(DevStates.waiting_ban_input)
    await state.update_data(dev_ban_action=action)
    if callback.message:
        await callback.message.answer(
            "🚫 Введите <code>USER_ID</code> и (при необходимости) причину через пробел, например:\n"
            "<code>123456789 Спам запросами</code>"
        )
    await callback.answer()


@router.message(DevStates.waiting_ban_input)
async def handle_dev_ban_input(message: Message, state: FSMContext, db_user: dict[str, Any]) -> None:
    uid = message.from_user.id if message.from_user else 0
    if not _authorized_dev(uid, db_user):
        await message.answer(DENIED_TEXT)
        return

    parts = (message.text or "").strip().split(maxsplit=1)
    if not parts or not parts[0].isdigit():
        await message.answer("⚠️ Укажите числовой <code>USER_ID</code>.")
        return

    target_id = int(parts[0])
    reason = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "Нарушение правил"
    data = await state.get_data()
    action = str(data.get("dev_ban_action", "lock"))
    await state.set_state(None)

    if is_developer(target_id):
        await message.answer("⛔ Нельзя заблокировать владельца DEVELOPER.", reply_markup=dev_bans_keyboard())
        return

    now_iso = datetime.now(config.tz).isoformat()
    if action == "lock":
        await db.conn.execute("UPDATE users SET is_banned = 1, ban_reason = ? WHERE user_id = ?", (reason, target_id))
        await db.conn.execute(
            "INSERT INTO bans (user_id, action, reason, actor_id, created_at) VALUES (?, 'BAN', ?, ?, ?)",
            (target_id, reason, uid, now_iso),
        )
        await log_admin_action(uid, "BAN_USER", target_id, reason)
        await db.conn.commit()
        await message.answer(f"🚫 Пользователь <code>{target_id}</code> заблокирован.", reply_markup=dev_bans_keyboard())
    elif action == "unlock":
        await db.conn.execute("UPDATE users SET is_banned = 0, ban_reason = NULL WHERE us