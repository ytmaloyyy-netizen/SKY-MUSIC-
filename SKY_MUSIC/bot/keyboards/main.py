from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.utils.permissions import Role, is_developer


def nav_row(back_callback: str = "menu:main", include_home: bool = True) -> list[InlineKeyboardButton]:
    row = [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]
    if include_home and back_callback != "menu:main":
        row.append(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"))
    return row


def main_menu_keyboard(user_id: int, role: Role) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="🎵 Обработка музыки", callback_data="menu:audio"),
            InlineKeyboardButton(text="🎚️ Аудиоэффекты", callback_data="menu:effects"),
        ],
        [
            InlineKeyboardButton(text="🌌 Пространственный звук", callback_data="menu:spatial"),
            InlineKeyboardButton(text="🎤 Работа с вокалом", callback_data="menu:vocals"),
        ],
        [
            InlineKeyboardButton(text="✏️ Редактор аудио", callback_data="menu:editor"),
            InlineKeyboardButton(text="🔎 Поиск музыки и текстов", callback_data="menu:search"),
        ],
        [
            InlineKeyboardButton(text="📂 Мои файлы", callback_data="menu:files"),
            InlineKeyboardButton(text="⭐ Premium", callback_data="menu:premium"),
        ],
        [
            InlineKeyboardButton(text="👤 Мой профиль", callback_data="menu:profile"),
            InlineKeyboardButton(text="❓ Помощь", callback_data="menu:help"),
        ],
    ]

    if role == Role.ADMIN and not is_developer(user_id, role):
        rows.append([InlineKeyboardButton(text="🛡️ Админ-инструменты", callback_data="menu:admin_tools")])

    if is_developer(user_id, role):
        rows.append([InlineKeyboardButton(text="👑 DEVELOPER PANEL", callback_data="dev:panel")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")]]
    )
