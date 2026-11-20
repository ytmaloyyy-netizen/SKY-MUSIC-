from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile
from bot.database.queries import get_quota_status, consume_processing_quota, add_processing_history
from bot.keyboards.effects import effects_menu_keyboard
from bot.utils.files import create_job_dir, cleanup_job_dir, sanitize_filename

logger = logging.getLogger("sky_music.effects")
router = Router(name="effects")


class EffectsStates(StatesGroup):
    waiting_input = State()


def _build_effect_filter(effect_key: str, intensity: float, extra: dict[str, Any]) -> tuple[str, list[str]]:
    k = max(0.1, min(2.0, float(intensity)))
    extra_inputs: list[str] = []

    if effect_key == "bass_boost":
        gain = round(6.0 * k, 2)
        return f"bass=g={gain}:f=110:w=0.6,alimiter=limit=0.95", extra_inputs
    if effect_key == "deep_bass":
        gain = round(9.0 * k, 2)
        return f"bass=g={gain}:f=68:w=0.5,lowpass=f=4500,alimiter=limit=0.95", extra_inputs
    if effect_key == "stereo_3d":
        delay = int(6 + 10 * k)
        return f"stereotools=mlev=1.0:slev={round(1.15 * k, 2)},aecho=0.8:0.8:{delay}:{round(0.25 * min(1.0, k), 2)},alimiter=limit=0.95", extra_inputs
    if effect_key == "wide_stereo":
        width = round(min(2.0, 1.25 * k), 2)
        return f"extrastereo=m={width}:c=1,alimiter=limit=0.95", extra_inputs
    if effect_key == "equalizer":
        b_gain = round(3.0 * k, 2)
        t_gain = round(3.5 * k, 2)
        return f"equalizer=f=120:width_type=o:w=1.0:g={b_gain},equalizer=f=3200:width_type=o:w=1.2:g={t_gain},alimiter=limit=0.95", extra_inputs
    if effect_key == "custom_eq":
        low_g = float(extra.get("eq_low", 3.0))
        mid_g = float(extra.get("eq_mid", 0.0))
        high_g = float(extra.get("eq_high", 3.0))
        return (
            f"equalizer=f=110:width_type=o:w=1.0:g={low_g},"
            f"equalizer=f=1000:width_type=o:w=1.2:g={mid_g},"
            f"equalizer=f=6000:width_type=o:w=1.2:g={high_g},alimiter=limit=0.95"
        ), extra_inputs
    if effect_key == "reverb":
        d1 = int(40 + 40 * min(1.5, k))
        d2 = int(85 + 75 * min(1.5, k))
        return f"aecho=0.85:0.85:{d1}|{d2}:{round(0.25 * min(1.2, k), 2)}|{round(0.18 * min(1.2, k), 2)},alimiter=limit=0.95", extra_inputs
    if effect_key == "hall_reverb":
        d1 = int(90 + 90 * min(1.5, k))
        d2 = int(180 + 170 * min(1.5, k))
        d3 = int(310 + 240 * min(1.5, k))
        return f"aecho=0.8:0.85:{d1}|{d2}|{d3}:0.35|0.26|0.20,alimiter=limit=0.95", extra_inputs
    if effect_key == "echo":
        delay_ms = int(220 + 280 * min(1.5, k))
        decay = round(min(0.75, 0.35 * k), 2)
        return f"aecho=0.85:0.85:{delay_ms}:{decay},alimiter=limit=0.95", extra_inputs
    if effect_key == "compressor":
        ratio = round(min(12.0, 3.0 + 3.0 * k), 1)
        return f"acompressor=threshold=-18dB:ratio={ratio}:attack=12:release=140:makeup=3dB,alimiter=limit=0.95", extra_inputs
    if effect_key == "denoise":
        return "highpass=f=85,lowpass=f=14500,afftdn=nr=12:nf=-25,alimiter=limit=0.95", extra_inputs
    if effect_key == "voice_enhance":
        return "highpass=f=100,equalizer=f=2800:width_type=o:w=1.2:g=4.5,acompressor=threshold=-16dB:ratio=3.5:attack=8:release=110:makeup=2.5dB,alimiter=limit=0.95", extra_inputs
    if effect_key == "fade_in":
        dur = round(max(1.0, 3.0 * k), 1)
        return f"afade=t=in:st=0:d={dur}", extra_inputs
    if effect_key == "fade_out":
        dur = round(max(1.0, 3.0 * k), 1)
        return f"areverse,afade=t=in:st=0:d={dur},areverse", extra_inputs
    if effect_key == "volume":
        vol = round(max(0.1, min(3.0, float(extra.get("volume_mult", k)))), 2)
        return f"volume={vol},alimiter=limit=0.95", extra_inputs
    if effect_key == "trim":
        start_sec = max(0.0, float(extra.get("trim_start", 0.0)))
        end_sec = float(extra.get("trim_end", 30.0))
        duration = max(1.0, end_sec - start_sec)
        return f"atrim=start={start_sec}:duration={duration},asetpts=PTS-STARTPTS", extra_inputs

    return "alimiter=limit=0.95", extra_inputs


def _run_ffmpeg_effect_sync(
    input_path: Path,
    second_input: Path | None,
    output_mp3: Path,
    effect_key: str,
    intensity: float,
    extra: dict[str, Any],
) -> Path:
    if effect_key == "merge" and second_input is not None:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-i", str(second_input),
            "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1,alimiter=limit=0.95[outa]",
            "-map", "[outa]",
            "-c:a", "libmp3lame", "-b:a", "320k",
            str(output_mp3),
        ]
    else:
        af_chain, _ = _build_effect_filter(effect_key, intensity, extra)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vn",
            "-af", af_chain,
            "-c:a", "libmp3lame", "-b:a", "320k",
            str(output_mp3),
        ]

    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        err_tail = (proc.stderr or "").strip().splitlines()[-5:]
        raise RuntimeError(f"Ошибка FFmpeg: {' | '.join(err_tail)}")
    return output_mp3


async def _render_effects_menu(target: Message | CallbackQuery, state: FSMContext, notice: str | None = None) -> None:
    data = await state.get_data()
    intensity = float(data.get("effects_intensity", 1.0))
    merge_ready = bool(data.get("merge_second_file_id"))
    file_line = f"<code>{data.get('source_name', 'track')}</code>" if data.get("source_file_id") else "<i>не выбран</i>"

    text = (
        "🎚️ <b>Дополнительные аудиоэффекты — SKY MUSIC</b>\n\n"
        f"• <b>Текущий файл:</b> {file_line}\n"
        f"• <b>Интенсивность:</b> <code>{int(round(intensity * 100))}%</code>\n"
        f"• <b>Второй трек для склейки:</b> <b>{'загружен' if merge_ready else 'не загружен'}</b>"
    )
    if notice:
        text = f"{notice}\n\n{text}"

    kb = effects_menu_keyboard(intensity=intensity, merge_queued=merge_ready)
    if isinstance(target, CallbackQuery):
        if target.message:
            try:
                await target.message.edit_text(text, reply_markup=kb)
            except Exception:
                await target.message.answer(text, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(F.data == "menu:effects")
async def cb_open_effects(callback: CallbackQuery, state: FSMContext) -> None:
    await _render_effects_menu(callback, state)


@router.callback_query(F.data.startswith("effect_custom:"))
async def cb_effect_custom(callback: CallbackQuery, state: FSMContext) -> None:
    kind = callback.data.split(":")[-1]
    prompts = {
        "intensity": ("intensity", "Введите интенсивность эффекта в процентах (<code>10</code>–<code>200</code>):"),
        "volume": ("volume", "Введите множитель громкости (например, <code>1.3</code> или <code>0.7</code>, диапазон <code>0.1</code>–<code>3.0</code>):"),
        "trim": ("trim", "Введите начало и конец обрезки в секундах через пробел (например, <code>10 45</code>):"),
        "eq": ("eq", "Введите 3 значения эквалайзера (НЧ СЧ ВЧ в дБ) через пробел (например, <code>4 -1 3</code>):"),
        "merge": ("merge", "Отправьте второй аудиофайл, который нужно объединить с текущим треком."),
    }
    if kind not in prompts:
        await callback.answer("Неизвестная настройка", show_alert=True)
        return

    mode_key, prompt_text = prompts[kind]
    await state.set_state(EffectsStates.waiting_input)
    await state.update_data(effect_custom_mode=mode_key)
    if callback.message:
        await callback.message.answer(f"🎛️ <b>Настройка эффекта</b>\n\n{prompt_text}")
    await callback.answer()


@router.message(EffectsStates.waiting_input)
async def handle_effect_custom_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    mode = data.get("effect_custom_mode")

    if mode == "merge":
        media = message.audio or message.voice or message.document
        if not media:
            await message.answer("⚠️ Отправьте второй аудиофайл для объединения.")
            return
        await state.update_data(
            merge_second_file_id=media.file_id,
            merge_second_name=getattr(media, "file_name", None) or "second_track.mp3",
        )
        await state.set_state(None)
        await _render_effects_menu(message, state, notice="🔗 Второй трек сохранён. Нажмите «🔗 Объединить» для склейки.")
        return

    raw = (message.text or "").strip().replace(",", ".")
    if mode == "intensity":
        try:
            pct = max(10.0, min(200.0, float(raw.replace("%", ""))))
        except ValueError:
            await message.answer("⚠️ Введите число от 10 до 200.")
            return
        await state.update_data(effects_intensity=round(pct / 100.0, 2))
        await state.set_state(None)
        await _render_effects_menu(message, state, notice=f"✅ Интенсивность установлена: {int(pct)}%.")
        return

    if mode == "volume":
        try:
            vol = max(0.1, min(3.0, float(raw)))
        except ValueError:
            await message.answer("⚠️ Введите число от 0.1 до 3.0.")
            return
        await state.update_data(volume_mult=vol)
        await state.set_state(None)
        await _run_effect_job(message, state, {}, "volume", f"🔀 Громкость ({vol}x)")
        return

    if mode == "trim":
        parts = raw.split()
        if len(parts) != 2:
            await message.answer("⚠️ Укажите два числа через пробел, например: <code>5 25</code>.")
            return
        try:
            s_val, e_val = float(parts[0]), float(parts[1])
            if e_val <= s_val:
                raise ValueError()
        except ValueError:
            await message.answer("⚠️ Конец обрезки должен быть больше начала.")
            return
        await state.update_data(trim_start=s_val, trim_end=e_val)
        await state.set_state(None)
        await _run_effect_job(message, state, {}, "trim", f"✂️ Обрезка ({s_val}s–{e_val}s)")
        return

    if mode == "eq":
        parts = raw.split()
        if len(parts) != 3:
            await message.answer("⚠️ Укажите 3 числа через пробел, например: <code>3 0 2</code>.")
            return
        try:
            l_val, m_val, h_val = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            await message.answer("⚠️ Все 3 значения должны быть числами.")
            return
        await state.update_data(eq_low=l_val, eq_mid=m_val, eq_high=h_val)
        await state.set_state(None)
        await _run_effect_job(message, state, {}, "custom_eq", f"🎛️ Custom EQ ({l_val}/{m_val}/{h_val} dB)")
        return


@router.callback_query(F.data.startswith("effect_run:"))
async def cb_run_effect(callback: CallbackQuery, state: FSMContext, db_user: dict[str, Any]) -> None:
    effect_key = callback.data.split(":", 1)[-1]
    if effect_key == "merge":
        data = await state.get_data()
        if not data.get("merge_second_file_id"):
            await callback.answer("Сначала загрузите второй трек через «🔗 Объединение аудио».", show_alert=True)
            return
    await _run_effect_job(callback, state, db_user, effect_key, f"🎚️ Эффект: {effect_key}")


async def _run_effect_job(
    target: Message | CallbackQuery,
    state: FSMContext,
    db_user: dict[str, Any],
    effect_key: str,
    label: str,
) -> None:
    data = await state.get_data()
    source_file_id = data.get("source_file_id")
    msg_target = target.message if isinstance(target, CallbackQuery) else target

    if not source_file_id or not msg_target:
        if isinstance(target, CallbackQuery):
            await target.answer("Сначала отправьте аудиофайл в студию.", show_alert=True)
        return

    if db_user:
        quota = await get_quota_status(db_user)
        if not quota["unlimited"] and (quota["remaining"] is None or quota["remaining"] <= 0):
            if isinstance(target, CallbackQuery):
                await target.answer("⚠️ Суточный лимит обработок исчерпан.", show_alert=True)
            return

    if isinstance(target, CallbackQuery):
        await target.answer()

    status_msg = await msg_target.answer(f"⏳ <b>Применение эффекта:</b> <b>{label}</b>...")
    user_id = int(db_user["user_id"]) if db_user else (target.from_user.id if target.from_user else 0)
    job_dir = create_job_dir(user_id)
    in_path = job_dir / sanitize_filename(data.get("source_name") or "effect_in")
    second_path: Path | None = None
    out_mp3 = job_dir / f"effect_{effect_key}.mp3"
    intensity = float(data.get("effects_intensity", 1.0))

    try:
        bot = target.bot
        assert bot is not None
        tg_file = await bot.get_file(source_file_id)
        if not tg_file.file_path:
            raise RuntimeError("Не удалось получить файл из Telegram.")
        await bot.download_file(tg_file.file_path, destination=in_path)

        if effect_key == "merge" and data.get("merge_second_file_id"):
            f2 = await bot.get_file(str(data["merge_second_file_id"]))
            if f2.file_path:
                second_path = job_dir / sanitize_filename(data.get("merge_second_name") or "second.mp3")
                await bot.download_file(f2.file_path, destination=second_path)

        result_file = await asyncio_to_thread_effect(
            in_path, second_path, out_mp3, effect_key, intensity, data
        )

        if db_user:
            await consume_processing_quota(db_user)
            await add_processing_history(
                user_id=user_id,
                category="effects",
                operation_name=label,
                status="completed",
            )

        await msg_target.answer_audio(
            audio=FSInputFile(result_file, filename=f"{Path(data.get('source_name') or 'track').stem}_{effect_key}.mp3"),
            caption=f"✅ <b>Готово — {label}</b>",
            reply_markup=effects_menu_keyboard(
                intensity=intensity,
                merge_queued=bool(data.get("merge_second_file_id")),
            ),
        )
        await status_msg.delete()
    except Exception as exc:
        logger.exception("Ошибка эффекта %s для user_id=%s", effect_key, user_id)
        await status_msg.edit_text(f"❌ <b>Ошибка применения эффекта:</b> <code>{exc}</code>")
    finally:
        cleanup_job_dir(job_dir)


async def asyncio_to_thread_effect(
    input_path: Path,
    second_input: Path | None,
    output_mp3: Path,
    effect_key: str,
    intensity: float,
    extra: dict[str, Any],
) -> Path:
    import asyncio
    return await asyncio.to_thread(
        _run_ffmpeg_effect_sync,
        input_path,
        second_input,
        output_mp3,
        effect_key,
        intensity,
        extra,
    )
