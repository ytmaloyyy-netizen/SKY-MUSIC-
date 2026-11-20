from __future__ import annotations

import html
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from bot.services.lyrics_search import search_tracks_itunes, search_lyrics_lrclib, format_track_results

router = Router(name="search")


class SearchStates(StatesGroup):
    waiting_query = State()


def _search_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔍 Найти песню по названию", callback_data="search:mode:song"),
                InlineKeyboardButton(text="🎤 Найти по исполнителю", callback_data="search:mode:artist"),
            ],
            [
                InlineKeyboardButton(text="📝 Найти текст песни", callback_data="search:mode:lyrics"),
                InlineKeyboardButton(text="🎧 Определить информацию", callback_data="search:mode:info"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:main"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main"),
            ],
        ]
    )


@router.callback_query(F.data == "menu:search")
async def cb_search_menu(callback: CallbackQuery) -> None:
    text = (
        "🔎 <b>Поиск музыки и текстов — SKY MUSIC</b>\n\n"
        "Выберите тип поиска и отправьте запрос текстом:\n"
        "• Поиск карточек треков, альбомов и превью\n"
        "• Безопасный вывод разрешённого фрагмента текста и источника (без нарушения авторских прав)"
    )
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=_search_menu_keyboard())
        except Exception:
            await callback.message.answer(text, reply_markup=_search_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("search:mode:"))
async def cb_search_mode(callback: CallbackQuery, state: FSMContext) -> None:
    mode = callback.data.split(":")[-1]
    prompts = {
        "song": "Введите название композиции:",
        "artist": "Введите имя исполнителя:",
        "lyrics": "Введите название песни или исполнителя для поиска фрагмента текста:",
        "info": "Введите название трека или исполнителя для получения информации:",
    }
    await state.set_state(SearchStates.waiting_query)
    await state.update_data(search_mode=mode)
    if callback.message:
        await callback.message.answer(f"🔎 <b>{prompts.get(mode, 'Введите запрос:')}</b>")
    await callback.answer()


@router.message(SearchStates.waiting_query)
async def handle_search_query(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    if not query:
        await message.answer("⚠️ Введите поисковый запрос.")
        return

    data = await state.get_data()
    mode = data.get("search_mode", "song")
    await state.set_state(None)

    if mode == "lyrics":
        res = await search_lyrics_lrclib(query)
        if not res:
            await message.answer("📝 Запись по запросу не найдена.", reply_markup=_search_menu_keyboard())
            return
        track_name = html.escape(str(res.get("trackName") or query))
        artist_name = html.escape(str(res.get("artistName") or "Неизвестен"))
        plain_lyrics = str(res.get("plainLyrics") or "").strip()
        lines = [l.strip() for l in plain_lyrics.splitlines() if l.strip()]
        snippet = html.escape("\n".join(lines[:4])) if lines else "Фрагмент текста отсутствует в открытой карточке."
        text = (
            f"📝 <b>{artist_name} — {track_name}</b>\n\n"
            f"<i>Разрешённый краткий фрагмент:</i>\n"
            f"<blockquote>{snippet}</blockquote>\n\n"
            "ℹ️ <i>Полные защищённые авторским правом тексты без лицензии не публикуются.</i>"
        )
        await message.answer(text, reply_markup=_search_menu_keyboard())
        return

    items = await search_tracks_itunes(query, limit=5)
    header_map = {
        "song": f"🔍 <b>Результаты по названию:</b> <code>{html.escape(query)}</code>",
        "artist": f"🎤 <b>Треки исполнителя:</b> <code>{html.escape(query)}</code>",
        "info": f"🎧 <b>Информация о композиции:</b> <code>{html.escape(query)}</code>",
    }
    formatted = format_track_results(header_map.get(mode, "🔎 <b>Результаты поиска:</b>"), items)
    await message.answer(formatted, reply_markup=_search_menu_keyboard(), disable_web_page_preview=True)
