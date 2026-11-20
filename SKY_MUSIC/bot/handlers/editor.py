from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from bot.database.queries import consume_processing_quota, add_processing_history
from bot.services.metadata_editor import AudioMetadataTags, edit_audio_metadata
from bot.utils.files import create_job_dir, cleanup_job_dir, sanitize_filename

logger = logging.getLogger("sky_music.editor")
router = Router(name="editor")


class EditorStates(StatesGroup):
    waiting_tag_value = State()
    waiting_cover_photo = State()


def _editor_keyboard(target_ext: str = "mp3") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Изменить название", callback_data="editor:set:title"),
                InlineKeyboardButton(text="👤 Изменить исполнителя", callback_data="editor:set:artist"),
            ],
            [
                InlineKeyboardButton(text="💿 Изменить альбом", callback_data="editor:set:album"),
                InlineKeyboardButton(text="🏷️ Изменить теги", callback_data="editor:set:tags"),
            ],
            [
                InlineKeyboardButton(text="🖼️ Изменить обложку", callback_data="editor:set:cover"),
                InlineKeyboardButton(text="🧹 Очистить метаданные", callback_data="editor:clear_meta"),
            ],
            [
                InlineKeyboardButton(text=f"🔄 Формат: {target_ext.upper()}", callback_data="editor:cycle_format"),
                InlineKeyboardButton(text="💾 Сохранить файл", callback_data="editor:save"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:main"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
            ],
        ]
    )


def _format_editor_text(data: dict[str, Any]) -> str:
    has_file = bool(data.get("source_file_id"))
    file_str = f"<code>{data.get('source_name', 'track')}</code>" if has_file else "<i>не загружен</i>"
    ext = str(data.get("editor_ext", "mp3")).upper()
    cover_str = "загружена" if data.get("editor_cover_file_id") else "не задана"

    return (
        "✏️ <b>Редактор аудио и метаданных — SKY MUSIC</b>\n\n"
        f"• <b>Файл:</b> {file_str}\n"
        f"• <b>Формат экспорта:</b> <code>{ext}</code>\n"
        f"• <b>Название:</b> <code>{data.get('meta_title') or '—'}</code>\n"
        f"• <b>Исполнитель:</b> <code>{data.get('meta_artist') or '—'}</code>\n"
        f"• <b>Альбом:</b> <code>{data.get('meta_album') or '—'}</code>\n"
        f"• <b>Год / Жанр:</b> <code>{data.get('meta_year') or '—'}</code> / <code>{data.get('meta_genre') or '—'}</code>\n"
        f"• <b>Трек / Комментарий:</b> <code>{data.get('meta_track') or '—'}</code> / <code>{data.get('meta_comment') or '—'}</code>\n"
        f"• <b>Обложка:</b> <b>{cover_str}</b>\n"
        f"• <b>Очистка старых тегов:</b> <b>{'Да' if data.get('meta_clear') else 'Нет'}</b>"
    )


async def _render_editor(target: Message | CallbackQuery, state: FSMContext, notice: str | None = None) -> None:
    data = await state.get_data()
    ext = str(data.get("editor_ext", "mp3"))
    text = _format_editor_text(data)
    if notice:
        text = f"{notice}\n\n{text}"
    kb = _editor_keyboard(ext)
    if isinstance(target, CallbackQuery):
        if target.message:
            try:
                await target.message.edit_text(text, reply_markup=kb)
            except Exception:
                await target.message.answer(text, reply_markup=kb)
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(F.data == "menu:editor")
async def cb_open_editor(callback: CallbackQuery, state: FSMContext) -> None:
    await _render_editor(callback, state)


@router.callback_query(F.data == "editor:cycle_format")
async def cb_cycle_format(callback: CallbackQuery, state: FSMContext) -> None:
    order = ["mp3", "flac", "m4a"]
    data = await state.get_data()
    cur = str(data.get("editor_ext", "mp3")).lower()
    nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "mp3"
    await state.update_data(editor_ext=nxt)
    await _render_editor(callback, state)


@router.callback_query(F.data == "editor:clear_meta")
async def cb_clear_meta(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    cur = not bool(data.get("meta_clear", False))
    await state.update_data(
        meta_clear=cur,
        meta_title=None if cur else data.get("meta_title"),
        meta_artist=None if cur else data.get("meta_artist"),
        meta_album=None if cur else data.get("meta_album"),
        meta_year=None if cur else data.get("meta_year"),
        meta_genre=None if cur else data.get("meta_genre"),
        meta_track=None if cur else data.get("meta_track"),
        meta_comment=None if cur else data.get("meta_comment"),
        editor_cover_file_id=None if cur else data.get("editor_cover_file_id"),
    )
    await _render_editor(callback, state, notice="🧹 Режим очистки метаданных переключён.")


@router.callback_query(F.data.startswith("editor:set:"))
async def cb_editor_set_field(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":")[-1]
    if field == "cover":
        await state.set_state(EditorStates.waiting_cover_photo)
        if callback.message:
            await callback.message.answer("🖼️ Отправьте изображение обложки (фото или файл JPG/PNG).")
        await callback.answer()
        return

    prompts = {
        "title": ("meta_title", "Введите новое название композиции:"),
        "artist": ("meta_artist", "Введите имя исполнителя:"),
        "album": ("meta_album", "Введите название альбома:"),
        "tags": (
            "bulk_tags",
            "Введите теги через точку с запятой (<code>;</code>) в формате:\n"
            "<code>Год; Жанр; Номер трека; Комментарий</code>\n"
            "Например: <code>2026; Electronic; 01; SKY MUSIC Studio</code>",
        ),
    }
    if field not in prompts:
        await callback.answer("Неизвестное поле", show_alert=True)
        return

    target_field, prompt_text = prompts[field]
    await state.set_state(EditorStates.waiting_tag_value)
    await state.update_data(editor_target_field=target_field)
    if callback.message:
        await callback.message.answer(f"✏️ <b>Редактирование метаданных</b>\n\n{prompt_text}")
    await callback.answer()


@router.message(EditorStates.waiting_cover_photo, F.photo | F.document)
async def handle_cover_upload(message: Message, state: FSMContext) -> None:
    photo_file_id: str | None = None
    if message.photo:
        photo_file_id = message.photo[-1].file_id
    elif message.document and (message.document.mime_type or "").startswith("image/"):
        photo_file_id = message.document.file_id

    if not photo_file_id:
        await message.answer("⚠️ Отправьте картинку (JPG или PNG) для обложки.")
        return

    await state.update_data(editor_cover_file_id=photo_file_id)
    await state.set_state(None)
    await _render_editor(message, state, notice="🖼️ Обложка прикреплена.")


@router.message(EditorStates.waiting_tag_value)
async def handle_tag_value_input(message: Message, state: FSMContext) -> None:
    val = (message.text or "").strip()
    if not val:
        await message.answer("⚠️ Значение не может быть пустым.")
        return

    data = await state.get_data()
    target_field = data.get("editor_target_field")

    if target_field == "bulk_tags":
        parts = [p.strip() for p in val.split(";")]
        updates: dict[str, Any] = {}
        if len(parts) >= 1 and parts[0]:
            updates["meta_year"] = parts[0]
        if len(parts) >= 2 and parts[1]:
            updates["meta_genre"] = parts[1]
        if len(parts) >= 3 and parts[2]:
            updates["meta_track"] = parts[2]
        if len(parts) >= 4 and parts[3]:
            updates["meta_comment"] = parts[3]
        await state.update_data(**updates)
    elif target_field in {"meta_title", "meta_artist", "meta_album"}:
        await state.update_data(**{str(target_field): val})

    await state.set_state(None)
    await _render_editor(message, state, notice="✅ Метаданные обновлены.")


@router.callback_query(F.data == "editor:save")
async def cb_editor_save(callback: CallbackQuery, state: FSMContext, db_user: dict[str, Any]) -> None:
    data = await state.get_data()
    source_file_id = data.get("source_file_id")
    if not source_file_id or not callback.message:
        await callback.answer("Сначала загрузите аудиофайл.", show_alert=True)
        return

    await callback.answer()
    status_msg = await callback.message.answer("💾 <b>Сохранение метаданных и конвертация файла...</b>")

    user_id = int(db_user["user_id"])
    job_dir = create_job_dir(user_id)
    in_path = job_dir / sanitize_filename(data.get("source_name") or "track.mp3")
    out_stem = job_dir / "edited_track"
    cover_path: Path | None = None

    try:
        bot = callback.bot
        assert bot is not None
        tg_file = await bot.get_file(source_file_id)
        if not tg_file.file_path:
            raise RuntimeError("Не удалось получить путь к аудиофайлу в Telegram.")
        await bot.download_file(tg_file.file_path, destination=in_path)

        cover_id = data.get("editor_cover_file_id")
        if cover_id:
            c_file = await bot.get_file(cover_id)
            if c_file.file_path:
                c_ext = Path(c_file.file_path).suffix or ".jpg"
                cover_path = job_dir / f"cover{c_ext}"
                await bot.download_file(c_file.file_path, destination=cover_path)

        tags = AudioMetadataTags(
            title=data.get("meta_title"),
            artist=data.get("meta_artist"),
            album=data.get("meta_album"),
            year=data.get("meta_year"),
            genre=data.get("meta_genre"),
            track_number=data.get("meta_track"),
            comment=data.get("meta_comment"),
            clear_existing=bool(data.get("meta_clear", False)),
        )
        target_ext = str(data.get("editor_ext", "mp3")).lower()
        final_file = await edit_audio_metadata(
            input_path=in_path,
            output_path=out_stem,
            tags=tags,
            cover_path=cover_path,
            target_ext=target_ext,
        )

        await consume_processing_quota(db_user)
        await add_processing_history(
            user_id=user_id,
            category="editor",
            operation_name=f"Редактор метаданных ({target_ext.upper()})",
            status="completed",
        )

        out_name = f"{Path(data.get('meta_title') or data.get('source_name') or 'edited').stem}.{target_ext}"
        await callback.message.answer_audio(
            audio=FSInputFile(final_file, filename=sanitize_filename(out_name)),
            caption=f"✅ <b>Метаданные сохранены</b> (<code>{target_ext.upper()}</code>)",
            reply_markup=_editor_keyboard(target_ext),
        )
        await status_msg.delete()
    except Exception as exc:
        logger.exception("Ошибка редактора аудио user_id=%s", user_id)
        await status_msg.edit_text(f"❌ <b>Ошибка сохранения метаданных:</b> <code>{exc}</code>")
    finally:
        cleanup_job_dir(job_dir)
