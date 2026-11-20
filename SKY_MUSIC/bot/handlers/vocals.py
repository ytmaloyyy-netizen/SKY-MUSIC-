from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile
from bot.database.queries import get_quota_status, consume_processing_quota, add_processing_history
from bot.keyboards.vocals import vocals_menu_keyboard
from bot.services.vocal_separator import SUPPORTED_VOCAL_MODES, separate_audio_stems
from bot.utils.files import create_job_dir, cleanup_job_dir, sanitize_filename

logger = logging.getLogger("sky_music.vocals")
router = Router(name="vocals")


@router.callback_query(F.data == "menu:vocals")
async def cb_vocals_menu(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    has_file = bool(data.get("source_file_id"))
    file_line = (
        f"• <b>Текущий файл:</b> <code>{data.get('source_name', 'track')}</code>"
        if has_file
        else "• <b>Текущий файл:</b> <i>не выбран (отправьте аудиофайл или выберите раздел обработки музыки)</i>"
    )
    text = (
        "🎤 <b>Работа с вокалом и дорожками — Demucs AI</b>\n\n"
        f"{file_line}\n\n"
        "Реальное нейросетевое разделение через <b>Demucs</b> (без имитации эквалайзером). "
        "Операция ресурсоёмкая и может занять больше времени на CPU."
    )
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=vocals_menu_keyboard())
        except Exception:
            await callback.message.answer(text, reply_markup=vocals_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("vocal_run:"))
async def cb_run_vocal_separation(callback: CallbackQuery, state: FSMContext, db_user: dict[str, Any]) -> None:
    mode = callback.data.split(":", 1)[-1]
    mode_label = SUPPORTED_VOCAL_MODES.get(mode)
    if not mode_label:
        await callback.answer("Неизвестный режим разделения", show_alert=True)
        return

    data = await state.get_data()
    source_file_id = data.get("source_file_id")
    if not source_file_id or not callback.message:
        await callback.answer("Сначала отправьте аудиофайл в чат.", show_alert=True)
        return

    quota = await get_quota_status(db_user)
    if not quota["unlimited"] and (quota["remaining"] is None or quota["remaining"] <= 0):
        await callback.answer("⚠️ Суточный лимит обработок исчерпан.", show_alert=True)
        return

    await callback.answer()
    status_msg = await callback.message.answer(
        f"⏳ <b>AI-разделение запущено:</b> <b>{mode_label}</b>\n"
        "Модель <b>Demucs</b> анализирует и разделяет дорожки..."
    )

    user_id = int(db_user["user_id"])
    job_dir = create_job_dir(user_id)
    in_path = job_dir / sanitize_filename(data.get("source_name") or "vocal_input")

    try:
        bot = callback.bot
        assert bot is not None
        tg_file = await bot.get_file(source_file_id)
        if not tg_file.file_path:
            raise RuntimeError("Telegram не вернул путь к исходному файлу.")
        await bot.download_file(tg_file.file_path, destination=in_path)

        stems = await separate_audio_stems(in_path, job_dir, mode=mode)
        await consume_processing_quota(db_user)
        await add_processing_history(
            user_id=user_id,
            category="vocals",
            operation_name=mode_label,
            parameters_json=f'{{"mode": "{mode}", "stems_count": {len(stems)}}}',
            status="completed",
        )

        base_stem = Path(data.get("source_name") or "track").stem
        for idx, (stem_title, stem_file) in enumerate(stems, start=1):
            await callback.message.answer_audio(
                audio=FSInputFile(stem_file, filename=f"{base_stem}_{idx}_{stem_file.stem}.mp3"),
                caption=f"🎤 <b>{stem_title}</b> — <i>SKY MUSIC (Demucs)</i>",
            )

        await status_msg.edit_text(
            f"✅ <b>Разделение завершено:</b> <b>{mode_label}</b>\n"
            f"Отправлено дорожек: <b>{len(stems)}</b>.",
            reply_markup=vocals_menu_keyboard(),
        )
    except Exception as exc:
        logger.exception("Ошибка разделения вокала для user_id=%s", user_id)
        await add_processing_history(
            user_id=user_id,
            category="vocals",
            operation_name=mode_label,
            parameters_json=f'{{"mode": "{mode}"}}',
            status="error",
            error_message=str(exc),
        )
        await status_msg.edit_text(
            "❌ <b>Ошибка при разделении дорожек</b>\n\n"
            f"Причина: <code>{exc}</code>\n"
            "Убедитесь, что пакет <code>demucs</code> и <code>ffmpeg</code> установлены на сервере."
        )
    finally:
        cleanup_job_dir(job_dir)
