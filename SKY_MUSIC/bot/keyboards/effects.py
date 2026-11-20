from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def effects_menu_keyboard(intensity: float = 1.0, merge_queued: bool = False) -> InlineKeyboardMarkup:
    pct = int(round(intensity * 100))
    merge_label = "🔗 Объединить (+2-й трек готов)" if merge_queued else "🔗 Объединение аудио"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔊 Bass Boost", callback_data="effect_run:bass_boost"),
                InlineKeyboardButton(text="🌊 Deep Bass", callback_data="effect_run:deep_bass"),
            ],
            [
                InlineKeyboardButton(text="🎧 3D Stereo", callback_data="effect_run:stereo_3d"),
                InlineKeyboardButton(text="🌌 Wide Stereo", callback_data="effect_run:wide_stereo"),
            ],
            [
                InlineKeyboardButton(text="🎼 Equalizer", callback_data="effect_run:equalizer"),
                InlineKeyboardButton(text="🎛️ Custom Equalizer", callback_data="effect_custom:eq"),
            ],
            [
                InlineKeyboardButton(text="🌫️ Reverb", callback_data="effect_run:reverb"),
                InlineKeyboardButton(text="🏛️ Hall Reverb", callback_data="effect_run:hall_reverb"),
            ],
            [
                InlineKeyboardButton(text="🌧️ Echo", callback_data="effect_run:echo"),
                InlineKeyboardButton(text="🎚️ Compressor", callback_data="effect_run:compressor"),
            ],
            [
                InlineKeyboardButton(text="🔇 Noise Reduction", callback_data="effect_run:denoise"),
                InlineKeyboardButton(text="🎙️ Voice Enhancer", callback_data="effect_run:voice_enhance"),
            ],
            [
                InlineKeyboardButton(text="🎵 Fade In", callback_data="effect_run:fade_in"),
                InlineKeyboardButton(text="🎵 Fade Out", callback_data="effect_run:fade_out"),
            ],
            [
                InlineKeyboardButton(text="✂️ Обрезка аудио", callback_data="effect_custom:trim"),
                InlineKeyboardButton(text="🔀 Изменение громкости", callback_data="effect_custom:volume"),
            ],
            [
                InlineKeyboardButton(text=merge_label, callback_data="effect_custom:merge"),
                InlineKeyboardButton(text=f"🎚️ Интенсивность: {pct}%", callback_data="effect_custom:intensity"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:main"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
            ],
        ]
    )
