from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile
from bot.database.queries import consume_processing_quota, add_processing_history
from bot.keyboards.spatial import spatial_hub_keyboard, spatial_tier_keyboard
from bot.services.spatial_audio import SPATIAL_MODES, process_spatial_audio
from bot.utils.files import create_job_dir, cleanup_job_dir, sanitize_filename
from bot.utils.permissions import can_use_spatial_audio, Role

logger = logging.getLogger("sky_music.spatial")
router = Router(name="spatial")

LOCK_MESSAGE = "🔒 Эта технология доступна только администраторам SKY MUSIC."


class SpatialStates(StatesGroup):
    waiting_intensity = State()


def _check_access(db_user: dict[str, Any]) -> bool:
    user_id = int(db_user["user_id"])
    role: Role = db_user["effective_role"]
    return can_use_spatial_audio(user_id, role)


@router.callback_query(F.data == "menu:spatial")
async def cb_spatial_hub(callback: CallbackQuery, state: FSMContext, db_user: dict[str, Any]) -> None:
    if not _check_access(db_user):
        await callback.answer(LOCK_MESSAGE, show_alert=True)
        return

    data = await state.get_data()
    intensity = float(data.get("spatial_intensity", 1.0))
    text = (
        "🌌 <b>Пространственный звук — SKY MUSIC</b>\n\n"
        "Доступно исключительно для <b>ADMIN</b> и <b>DEVELOPER</b>.\n"
        f"Текущая интенсивность: <code>{int(intensity * 100)}%</code>\n\n"
        "<i>Техническое примечание: стандартный аудиопоток Telegram использует стерео (2 канала). "
        "Режимы 8D, 16D и 32D реализуют многослойное стереопанорамирование, траектории движения, "
        "микрозадержки глубины и атмосферную реверберацию, а не физический 32-канальный массив колонок.</i>"
    )
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=spatial_hub_keyboard(intensity))
        except Exception:
            await callback.message.answer(text, reply_markup=spatial_hub_keyboard(intensity))
    await callback.answer()


@router.callback_query(F.data.startswith("spatial:tier:"))
async def cb_spatial_tier(callback: CallbackQuery, state: FSMContext, db_user: dict[str, Any]) -> None:
    if not _check_access(db_user):
        await callback.answer(LOCK_MESSAGE, show_alert=True)
        return

    tier = callback.data.split(":")[-1]
    data = await state.get_data()
    intensity = float(data.get("spatial_intensity", 1.0))

    text = (
        f"🌌 <b>{tier} AUDIO — Выбор траектории</b>\n\n"
        f"Интенсивность: <code>{int(intensity * 100)}%</code>\n"
        "Выберите режим передвижения звукового образа и атмосферы:"
    )
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=spatial_tier_keyboard(tier, intensity))
        except Exception:
            await callback.message.answer(text, reply_markup=spatial_tier_keyboard(tier, intensity))
    await callback.answer()


@router.callback_query(F.data == "spatial:set_intensity")
async def cb_ask_intensity(callback: CallbackQuery, state: FSMContext, db_user: dict[str, Any]) -> None:
    if not _check_access(db_user):
        await callback.answer(LOCK_MESSAGE, show_alert=True)
        return

    await state.set_state(SpatialStates.waiting_intensity)
    if callback.message:
        await callback.message.answer(
            "🎚️ <b>Настройка интенсивности пространственного эффекта</b>\n\n"
            "Введите значение в процентах от <code>10</code> до <code>150</code> (например, <code>100</code>):"
        )
    await callback.answer()


@router.message(SpatialStates.waiting_intensity)
async def handle_spatial_intensity(message: Message, state: FSMContext, db_user: dict[str, Any]) -> None:
    if not _check_access(db_user):
        await message.answer(LOCK_MESSAGE)
        await state.set_state(None)
        return

    raw = (message.text or "").strip().replace("%", "").replace(",", ".")
    try:
        pct = float(raw)
    except ValueError:
        await message.answer("⚠️ Введите число от 10 до 150, например <code>100</code>.")
        return

    pct = max(10.0, min(150.0, pct))
    intensity = round(pct / 100.0, 2)
    await state.update_data(spatial_intensity=intensity)
    await state.set_state(None)
    await message.answer(
        f"✅ Интенсивность пространственного звука установлена: <code>{int(intensity * 100)}%</code>",
        reply_markup=spatial_hub_keyboard(intensity),
    )


@router.callback_query(F.data.startswith("spatial_run:"))
async def cb_run_spatial(callback: CallbackQuery, state: FSMContext, db_user: dict[str, Any]) -> None:
    if not _check_access(db_user):
        await callback.answer(LOCK_MESSAGE, show_alert=True)
        return

    mode_key = callback.data.split(":", 1)[-1]
    mode_cfg = SPATIAL_MODES.get(mode_key)
    if not mode_cfg:
        await callback.answer("Режим не найден", show_alert=True)
        return

    data = await state.get_data()
    source_file_id = data.get("source_file_id")
    if not source_file_id or not callback.message:
        await callback.answer("Сначала отправьте аудиофайл в студии.", show_alert=True)
        return

    intensity = float(data.get("spatial_intensity", 1.0))
    await callback.answer()
    status_msg = await callback.message.answer(
        f"🌌 <b>Генерация {mode_cfg.tier} AUDIO ({mode_cfg.mode_title})</b>\n"
        f"Интенсивность: <code>{int(intensity * 100)}%</code>..."
    )

    user_id = int(db_user["user_id"])
    job_dir = create_job_dir(user_id)
    in_path = job_dir / sanitize_filename(data.get("source_name") or "spatial_input")
    out_stem = job_dir / f"spatial_{mode_key}"

    try:
        bot = callback.bot
        assert bot is not None
        tg_file = await bot.get_file(source_file_id)
        if not tg_file.file_path:
            raise RuntimeError("Не удалось получить путь к файлу в Telegram.")
        await bot.download_file(tg_file.file_path, destination=in_path)

        result_path = await process_spatial_audio(in_path, out_stem, mode_cfg, intensity=intensity)
        await consume_processing_quota(db_user)
        await add_processing_history(
            user_id=user_id,
            category="spatial",
            operation_name=f"{mode_cfg.tier} — {mode_cfg.mode_title}",
            parameters_json=mode_cfg.to_json(intensity),
            status="completed",
        )

        await callback.message.answer_audio(
            audio=FSInputFile(result_path, filename=f"{Path(data.get('source_name') or 'track').stem}_{mode_key}.mp3"),
            caption=(
                f"🌌 <b>{mode_cfg.tier} AUDIO — {mode_cfg.mode_title}</b>\n"
                f"Интенсивность: <code>{int(intensity * 100)}%</code>"
            ),
            reply_markup=spatial_hub_keyboard(intensity),
        )
        await status_msg.delete()
    except Exception as exc:
        logger.exception("Ошибка пространственной обработки user_id=%s", user_id)
        await add_processing_history(
            user_id=user_id,
            category="spatial",
            operation_name=f"{mode_cfg.tier} — {mode_cfg.mode_title}",
            parameters_json=mode_cfg.to_json(intensity),
            status="error",
            error_message=str(exc),
        )
        await status_msg.edit_text(f"❌ <b>Ошибка пространственной обработки:</b> <code>{exc}</code>")
    finally:
        cleanup_job_dir(job_dir)

