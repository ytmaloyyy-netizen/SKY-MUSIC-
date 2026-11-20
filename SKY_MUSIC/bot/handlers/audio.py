from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile
from config import config
from bot.database.queries import (
    get_quota_status,
    consume_processing_quota,
    add_processing_history,
    register_user_file,
)
from bot.keyboards.audio import audio_studio_keyboard, after_audio_result_keyboard
from bot.services.audio_processor import (
    AudioTransformParams,
    PRESETS,
    process_audio_file,
)
from bot.utils.files import (
    create_job_dir,
    cleanup_job_dir,
    sanitize_filename,
    ALLOWED_AUDIO_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
)

logger = logging.getLogger("sky_music.audio")
router = Router(name="audio")


class AudioStudioStates(StatesGroup):
    waiting_parameter_value = State()


def _extract_incoming_media(message: Message) -> tuple[str, str, int, str] | None:
    """Возвращает (file_id, file_unique_id, file_size, suggested_name)."""
    if message.audio:
        a = message.audio
        return a.file_id, a.file_unique_id, int(a.file_size or 0), a.file_name or "track.mp3"
    if message.voice:
        v = message.voice
        return v.file_id, v.file_unique_id, int(v.file_size or 0), "voice_note.ogg"
    if message.video:
        vid = message.video
        return vid.file_id, vid.file_unique_id, int(vid.file_size or 0), vid.file_name or "video_track.mp4"
    if message.document:
        doc = message.document
        ext = Path(doc.file_name or "").suffix.lower()
        if ext in ALLOWED_AUDIO_EXTENSIONS or ext in ALLOWED_VIDEO_EXTENSIONS:
            return doc.file_id, doc.file_unique_id, int(doc.file_size or 0), doc.file_name or f"file{ext}"
    return None


def _studio_header(state_data: dict[str, Any]) -> str:
    has_file = bool(state_data.get("source_file_id"))
    file_label = f"<code>{state_data.get('source_name', 'аудиофайл')}</code>" if has_file else "<i>не загружен (отправьте аудио, голос, видео или документ)</i>"
    speed = float(state_data.get("speed", 1.0))
    pitch = float(state_data.get("pitch", 0.0))
    preserve_pitch = bool(state_data.get("preserve_pitch", False))
    bass_db = float(state_data.get("bass_db", 0.0))
    reverb = float(state_data.get("reverb", 0.0))

    return (
        "🎵 <b>Обработка музыки — SKY MUSIC</b>\n\n"
        f"• <b>Файл:</b> {file_label}\n"
        f"• <b>Скорость:</b> <code>{speed:.2f}x</code>\n"
        f"• <b>Тональность:</b> <code>{pitch:+.1f}</code> полутонов\n"
        f"• <b>Сохранение высоты голоса:</b> <b>{'Да' if preserve_pitch else 'Нет'}</b>\n"
        f"• <b>Басы:</b> <code>{bass_db:+.1f} dB</code>\n"
        f"• <b>Реверберация:</b> <code>{int(reverb * 100)}%</code>\n\n"
        "Выберите готовый пресет или настройте параметры вручную:"
    )


async def _render_studio(target: Message | CallbackQuery, state: FSMContext, notice: str | None = None) -> None:
    data = await state.get_data()
    text = _studio_header(data)
    if notice:
        text = f"{notice}\n\n{text}"
    kb = audio_studio_keyboard(
        speed=float(data.get("speed", 1.0)),
        pitch=float(data.get("pitch", 0.0)),
        preserve_pitch=bool(data.get("preserve_pitch", False)),
        bass_db=float(data.get("bass_db", 0.0)),
        reverb=float(data.get("reverb", 0.0)),
    )
    if isinstance(target, CallbackQuery):
        if target.message:
            try:
                await target.message.edit_text(text, reply_markup=kb)
            except Exception:
                await target.message.answer(text, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(F.data == "menu:audio")
async def cb_open_audio_menu(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    defaults = {
        "speed": data.get("speed", 1.0),
        "pitch": data.get("pitch", 0.0),
        "preserve_pitch": data.get("preserve_pitch", False),
        "bass_db": data.get("bass_db", 0.0),
        "reverb": data.get("reverb", 0.0),
    }
    await state.update_data(**defaults)
    await _render_studio(callback, state)


@router.message(F.audio | F.voice | F.video | F.document)
async def handle_incoming_media(message: Message, state: FSMContext, db_user: dict[str, Any]) -> None:
    extracted = _extract_incoming_media(message)
    if not extracted:
        return

    file_id, file_unique_id, file_size, suggested_name = extracted
    if file_size > config.max_file_size_bytes:
        await message.answer(
            f"⚠️ <b>Файл слишком большой</b>\n\n"
            f"Максимальный размер файла: <b>{config.max_file_size_mb} МБ</b>."
        )
        return

    safe_name = sanitize_filename(suggested_name)
    await register_user_file(
        user_id=int(db_user["user_id"]),
        file_unique_id=file_unique_id,
        telegram_file_id=file_id,
        file_name=safe_name,
        mime_type=message.document.mime_type if message.document else None,
        file_size=file_size,
    )
    await state.update_data(
        source_file_id=file_id,
        source_name=safe_name,
        speed=1.0,
        pitch=0.0,
        preserve_pitch=False,
        bass_db=0.0,
        reverb=0.0,
    )
    await _render_studio(message, state, notice=f"✅ Файл <code>{safe_name}</code> загружен в студию.")


@router.callback_query(F.data == "audio:toggle:preserve_pitch")
async def cb_toggle_preserve_pitch(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    current = bool(data.get("preserve_pitch", False))
    await state.update_data(preserve_pitch=not current)
    await _render_studio(callback, state)


@router.callback_query(F.data.startswith("audio:custom:"))
async def cb_ask_custom_param(callback: CallbackQuery, state: FSMContext) -> None:
    param_key = callback.data.split(":")[-1]
    prompts = {
        "speed": ("speed", "Введите скорость воспроизведения (например, <code>0.85</code> или <code>1.25</code>, диапазон 0.50–2.00):"),
        "pitch": ("pitch", "Введите сдвиг тона в полутонах (например, <code>-2.5</code> или <code>+4</code>, диапазон -12.0 до +12.0):"),
        "bass": ("bass_db", "Введите усиление басов в дБ (например, <code>6.0</code> или <code>-2.0</code>, диапазон -10.0 до +15.0):"),
        "reverb": ("reverb", "Введите уровень реверберации в процентах от <code>0</code> до <code>100</code>:"),
    }
    if param_key not in prompts:
        await callback.answer("Неизвестный параметр", show_alert=True)
        return

    field_name, prompt_text = prompts[param_key]
    await state.set_state(AudioStudioStates.waiting_parameter_value)
    await state.update_data(pending_param=field_name)
    if callback.message:
        await callback.message.answer(f"🎛️ <b>Настройка параметра</b>\n\n{prompt_text}")
    await callback.answer()


@router.message(AudioStudioStates.waiting_parameter_value)
async def handle_custom_param_input(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip().replace(",", ".")
    try:
        val = float(raw)
    except ValueError:
        await message.answer("⚠️ Введите корректное число, например <code>1.15</code> или <code>-2</code>.")
        return

    data = await state.get_data()
    field = data.get("pending_param")
    if field == "speed":
        val = max(0.5, min(2.0, val))
        await state.update_data(speed=val)
    elif field == "pitch":
        val = max(-12.0, min(12.0, val))
        await state.update_data(pitch=val)
    elif field == "bass_db":
        val = max(-10.0, min(15.0, val))
        await state.update_data(bass_db=val)
    elif field == "reverb":
        pct = max(0.0, min(100.0, val))
        await state.update_data(reverb=pct / 100.0)

    await state.set_state(None)
    await _render_studio(message, state, notice="✅ Параметр обновлён.")


@router.callback_query(F.data == "audio:reedit_last")
async def cb_reedit_last_result(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    last_id = data.get("last_result_file_id")
    if not last_id:
        await callback.answer("Нет готового результата для повторного редактирования.", show_alert=True)
        return
    await state.update_data(
        source_file_id=last_id,
        source_name=data.get("last_result_name") or "result_track.mp3",
    )
    await _render_studio(callback, state, notice="♻️ Последний результат загружен для повторной обработки.")


@router.callback_query(F.data.startswith("audio:preset:"))
async def cb_run_preset(callback: CallbackQuery, state: FSMContext, db_user: dict[str, Any]) -> None:
    preset_key = callback.data.split(":")[-1]
    preset = PRESETS.get(preset_key)
    if not preset:
        await callback.answer("Пресет не найден", show_alert=True)
        return

    await state.update_data(
        speed=preset.speed_factor,
        pitch=preset.pitch_semitones,
        preserve_pitch=preset.preserve_pitch,
        bass_db=preset.bass_db,
        reverb=preset.reverb_amount,
    )
    await _execute_audio_job(callback, state, db_user, preset)


@router.callback_query(F.data == "run_audio_custom")
async def cb_run_custom(callback: CallbackQuery, state: FSMContext, db_user: dict[str, Any]) -> None:
    data = await state.get_data()
    params = AudioTransformParams(
        preset_name="🎛️ Custom Mix",
        speed_factor=float(data.get("speed", 1.0)),
        pitch_semitones=float(data.get("pitch", 0.0)),
        preserve_pitch=bool(data.get("preserve_pitch", False)),
        bass_db=float(data.get("bass_db", 0.0)),
        reverb_amount=float(data.get("reverb", 0.0)),
    )
    await _execute_audio_job(callback, state, db_user, params)


async def _execute_audio_job(
    callback: CallbackQuery,
    state: FSMContext,
    db_user: dict[str, Any],
    params: AudioTransformParams,
) -> None:
    data = await state.get_data()
    source_file_id = data.get("source_file_id")
    if not source_file_id or not callback.message:
        await callback.answer("Сначала отправьте аудиофайл, голос, видео или документ.", show_alert=True)
        return

    quota = await get_quota_status(db_user)
    if not quota["unlimited"] and (quota["remaining"] is None or quota["remaining"] <= 0):
        await callback.answer("⚠️ Суточный лимит обработок исчерпан.", show_alert=True)
        await callback.message.answer(
            "⚠️ <b>Лимит обработок на сегодня исчерпан</b>\n\n"
            "Лимит сбрасывается автоматически в начале новых суток по часовому поясу сервера "
            "или может быть расширен в тарифе <b>🌟 PREMIUM</b>."
        )
        return

    await callback.answer()
    status_msg = await callback.message.answer(
        f"⏳ <b>Обработка запущена:</b> <b>{params.preset_name}</b>\n"
        "Пожалуйста, подождите — выполняется DSP-преобразование..."
    )

    user_id = int(db_user["user_id"])
    job_dir = create_job_dir(user_id)
    in_path = job_dir / sanitize_filename(data.get("source_name") or "input_audio")
    out_stem = job_dir / "processed_output"

    try:
        bot = callback.bot
        assert bot is not None
        tg_file = await bot.get_file(source_file_id)
        if not tg_file.file_path:
            raise RuntimeError("Telegram не вернул путь к файлу.")
        await bot.download_file(tg_file.file_path, destination=in_path)

        final_file = await process_audio_file(in_path, out_stem, params)
        allowed_to_spend = await consume_processing_quota(db_user)
        if not allowed_to_spend:
            raise RuntimeError("Недостаточно квоты обработок.")

        await add_processing_history(
            user_id=user_id,
            category="audio",
            operation_name=params.preset_name,
            parameters_json=params.to_json(),
            status="completed",
        )

        sent_msg = await callback.message.answer_audio(
            audio=FSInputFile(final_file, filename=f"{Path(data.get('source_name') or 'track').stem}_{params.output_format}"),
            caption=(
                f"✅ <b>Готово — {params.preset_name}</b>\n"
                f"Скорость: <code>{params.speed_factor:.2f}x</code> | "
                f"Тон: <code>{params.pitch_semitones:+.1f}</code> | "
                f"Басы: <code>{params.bass_db:+.1f} dB</code> | "
                f"Реверб: <code>{int(params.reverb_amount * 100)}%</code>"
            ),
            reply_markup=after_audio_result_keyboard(),
        )
        if sent_msg.audio:
            await state.update_data(
                last_result_file_id=sent_msg.audio.file_id,
                last_result_name=sent_msg.audio.file_name or "processed.mp3",
            )
        await status_msg.delete()
    except Exception as exc:
        logger.exception("Ошибка обработки аудио для user_id=%s", user_id)
        await add_processing_history(
            user_id=user_id,
            category="audio",
            operation_name=params.preset_name,
            parameters_json=params.to_json(),
            status="error",
            error_message=str(exc),
        )
        await status_msg.edit_text(
            "❌ <b>Ошибка при обработке аудио</b>\n\n"
            f"Причина: <code>{exc}</code>\n"
            "Проверьте формат и целостность файла или попробуйте другой трек."
        )
    finally:
        cleanup_job_dir(job_dir)
