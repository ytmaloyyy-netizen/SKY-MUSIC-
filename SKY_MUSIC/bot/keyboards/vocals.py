from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def vocals_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎤 Убрать вокал", callback_data="vocal_run:no_vocals"),
                InlineKeyboardButton(text="🎙️ Оставить только вокал", callback_data="vocal_run:vocals_only"),
            ],
            [
                InlineKeyboardButton(text="🥁 Оставить ударные", callback_data="vocal_run:drums_only"),
                InlineKeyboardButton(text="🎸 Оставить инструменты", callback_data="vocal_run:instruments_only"),
            ],
            [
                InlineKeyboardButton(text="🎚️ Извлечь бас", callback_data="vocal_run:bass_only"),
                InlineKeyboardButton(text="🎼 Извлечь мелодию", callback_data="vocal_run:melody_only"),
            ],
            [
                InlineKeyboardButton(text="🎹 Разделить музыку на дорожки", callback_data="vocal_run:all_stems"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:main"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
            ],
        ]
    )
