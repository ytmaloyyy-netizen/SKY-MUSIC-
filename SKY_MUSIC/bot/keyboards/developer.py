from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def developer_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Пользователи", callback_data="dev:users"),
                InlineKeyboardButton(text="👑 Управление ролями", callback_data="dev:roles"),
            ],
            [
                InlineKeyboardButton(text="🎟️ Лимиты", callback_data="dev:limits"),
                InlineKeyboardButton(text="🚫 Блокировки", callback_data="dev:bans"),
            ],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="dev:stats"),
                InlineKeyboardButton(text="⚙️ Настройки бота", callback_data="dev:settings"),
            ],
            [
                InlineKeyboardButton(text="📢 Рассылка", callback_data="dev:broadcast"),
                InlineKeyboardButton(text="📜 Журнал", callback_data="dev:logs"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:main"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
            ],
        ]
    )


def dev_roles_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Выдать ADMIN", callback_data="dev_act:role:ADMIN"),
                InlineKeyboardButton(text="➖ Снять ADMIN", callback_data="dev_act:role:DEFAULT"),
            ],
            [
                InlineKeyboardButton(text="⭐ Выдать PREMIUM", callback_data="dev_act:role:PREMIUM"),
                InlineKeyboardButton(text="🛑 Снять PREMIUM", callback_data="dev_act:role:DEFAULT"),
            ],
            [
                InlineKeyboardButton(text="📋 Список ADMIN / PREMIUM", callback_data="dev:list_privileged"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="dev:panel"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
            ],
        ]
    )


def dev_limits_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Доп. обработки", callback_data="dev_act:limit:bonus"),
                InlineKeyboardButton(text="🎯 Индивид. лимит", callback_data="dev_act:limit:custom"),
            ],
            [
                InlineKeyboardButton(text="🔄 Сбросить лимит", callback_data="dev_act:limit:reset"),
                InlineKeyboardButton(text="♾️ Безлимит юзеру", callback_data="dev_act:limit:unlimited"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Суточный DEFAULT", callback_data="dev_act:limit:default_cap"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="dev:panel"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
            ],
        ]
    )


def dev_bans_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚫 Заблокировать", callback_data="dev_act:ban:lock"),
                InlineKeyboardButton(text="✅ Разблокировать", callback_data="dev_act:ban:unlock"),
            ],
            [
                InlineKeyboardButton(text="⚠️ Выдать предупреждение", callback_data="dev_act:ban:warn"),
                InlineKeyboardButton(text="📜 Истории варнов/банов", callback_data="dev:ban_history"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="dev:panel"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
            ],
        ]
    )


def dev_settings_keyboard(maintenance: bool, reg_open: bool) -> InlineKeyboardMarkup:
    maint_btn = "🟢 Выключить тех. работы" if maintenance else "🛠️ Включить тех. работы"
    reg_btn = "🔒 Закрыть регистрацию" if reg_open else "🔓 Открыть регистрацию"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=maint_btn, callback_data="dev_toggle:maintenance")],
            [InlineKeyboardButton(text=reg_btn, callback_data="dev_toggle:registration")],
            [InlineKeyboardButton(text="📄 Ошибки из logs/errors.log", callback_data="dev:errors_log")],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="dev:panel"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
            ],
        ]
    )


def dev_broadcast_audience_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Всем пользователям", callback_data="dev_bc_aud:all"),
                InlineKeyboardButton(text="🌟 Только PREMIUM", callback_data="dev_bc_aud:premium"),
            ],
            [
                InlineKeyboardButton(text="🎧 Только DEFAULT", callback_data="dev_bc_aud:default"),
                InlineKeyboardButton(text="🛡️ Только ADMIN", callback_data="dev_bc_aud:admin"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="dev:panel"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
            ],
        ]
                )

def dev_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отправить рассылку", callback_data="dev_bc_confirm:yes"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="dev_bc_confirm:no"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="dev:broadcast"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
            ],
        ]
    )
    
