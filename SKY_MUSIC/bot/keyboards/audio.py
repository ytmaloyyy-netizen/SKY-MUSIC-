from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def audio_studio_keyboard(
    speed: float = 1.0,
    pitch: float = 0.0,
    preserve_pitch: bool = False,
    bass_db: float = 0.0,
    reverb: float = 0.0,
) -> InlineKeyboardMarkup:
    pitch_mode_label = "🎙️ Голос: сохранён" if preserve_pitch else "🎼 Голос: по тону"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🐢 Slowed", callback_data="audio:preset:slowed"),
                InlineKeyboardButton(text="🐌 Ultra Slowed", callback_data="audio:preset:ultra_slowed"),
            ],
            [
                InlineKeyboardButton(text="⚡ Speed Up", callback_data="audio:preset:speed_up"),
                InlineKeyboardButton(text="🚀 Ultra Speed Up", callback_data="audio:preset:ultra_speed_up"),
            ],
            [
                InlineKeyboardButton(text="🎧 Nightcore", callback_data="audio:preset:nightcore"),
                InlineKeyboardButton(text="🌙 Slowed + Reverb", callback_data="audio:preset:slowed_reverb"),
            ],
            [
                InlineKeyboardButton(text="🔊 Bass Boost", callback_data="audio:preset:bass_boost"),
                InlineKeyboardButton(text="🔄 Вернуть оригинал", callback_data="audio:preset:original"),
            ],
            [
                InlineKeyboardButton(text="🎼 Pitch Up (+3)", callback_data="audio:preset:pitch_up"),
                InlineKeyboardButton(text="🎼 Pitch Down (-3)", callback_data="audio:preset:pitch_down"),
            ],
            [
                InlineKeyboardButton(text=f"🎚️ Custom Speed ({speed:.2f}x)", callback_data="audio:custom:speed"),
                InlineKeyboardButton(text=f"🎛️ Custom Pitch ({pitch:+.1f})", callback_data="audio:custom:pitch"),
            ],
            [
                InlineKeyboardButton(text=pitch_mode_label, callback_data="audio:toggle:preserve_pitch"),
            ],
            [
                InlineKeyboardButton(text=f"🔊 Басы: {bass_db:+.1f} dB", callback_data="audio:custom:bass"),
                InlineKeyboardButton(text=f"🌫️ Реверб: {int(reverb * 100)}%", callback_data="audio:custom:reverb"),
            ],
            [
                InlineKeyboardButton(text="▶️ Применить текущие настройки", callback_data="run_audio_custom"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:main"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
            ],
        ]
    )


def after_audio_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎛️ Повторно редактировать результат", callback_data="audio:reedit_last")],
            [
                InlineKeyboardButton(text="🎵 Ещё обработка", callback_data="menu:audio"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
            ],
        ]
    )
