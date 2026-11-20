from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def spatial_hub_keyboard(intensity: float = 1.0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌌 8D AUDIO", callback_data="spatial:tier:8D")],
            [InlineKeyboardButton(text="🌌 16D AUDIO", callback_data="spatial:tier:16D")],
            [InlineKeyboardButton(text="🌌 32D AUDIO", callback_data="spatial:tier:32D")],
            [InlineKeyboardButton(text=f"🎚️ Интенсивность: {int(intensity * 100)}%", callback_data="spatial:set_intensity")],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:main"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
            ],
        ]
    )


def spatial_tier_keyboard(tier: str, intensity: float = 1.0) -> InlineKeyboardMarkup:
    tier_lower = tier.lower()
    if tier == "8D":
        modes = [
            ("Classic Orbit", "8d_classic_orbit"),
            ("Smooth Rotation", "8d_smooth_rotation"),
            ("Deep Space", "8d_deep_space"),
            ("Atmospheric", "8d_atmospheric"),
        ]
    elif tier == "16D":
        modes = [
            ("Double Orbit", "16d_double_orbit"),
            ("Hyper Rotation", "16d_hyper_rotation"),
            ("Deep Atmosphere", "16d_deep_atmosphere"),
            ("Surround Motion", "16d_surround_motion"),
        ]
    else:
        modes = [
            ("Ultimate Space", "32d_ultimate_space"),
            ("Infinity Orbit", "32d_infinity_orbit"),
            ("Hyper Atmosphere", "32d_hyper_atmosphere"),
            ("Advanced Motion", "32d_advanced_motion"),
        ]

    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(modes), 2):
        pair = modes[i : i + 2]
        rows.append(
            [
                InlineKeyboardButton(text=f"✨ {title}", callback_data=f"spatial_run:{key}")
                for title, key in pair
            ]
        )

    rows.append([InlineKeyboardButton(text=f"🎚️ Интенсивность: {int(intensity * 100)}%", callback_data="spatial:set_intensity")])
    rows.append(
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:spatial"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
