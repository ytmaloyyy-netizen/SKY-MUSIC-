from __future__ import annotations

import html
from typing import Any
import aiohttp


async def search_tracks_itunes(query: str, limit: int = 5) -> list[dict[str, Any]]:
    url = "https://itunes.apple.com/search"
    params = {"term": query, "media": "music", "entity": "song", "limit": str(limit)}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return []
            payload = await resp.json(content_type=None)
            return list(payload.get("results") or [])


async def search_lyrics_lrclib(query: str) -> dict[str, Any] | None:
    url = "https://lrclib.net/api/search"
    params = {"q": query}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return None
            items = await resp.json(content_type=None)
            if isinstance(items, list) and items:
                return items[0]
            return None


def format_track_results(title_header: str, items: list[dict[str, Any]]) -> str:
    if not items:
        return f"{title_header}\n\nНичего не найдено по вашему запросу."
    lines = [title_header, ""]
    for idx, item in enumerate(items[:5], start=1):
        track = html.escape(str(item.get("trackName") or "Неизвестный трек"))
        artist = html.escape(str(item.get("artistName") or "Неизвестный исполнитель"))
        album = html.escape(str(item.get("collectionName") or "—"))
        genre = html.escape(str(item.get("primaryGenreName") or "—"))
        preview_url = item.get("previewUrl")
        line = f"<b>{idx}. {artist} — {track}</b>\n💿 Альбом: <code>{album}</code> | 🏷️ <code>{genre}</code>"
        if preview_url:
            line += f"\n🎧 <a href=\"{html.escape(str(preview_url))}\">Превью-фрагмент (30 сек)</a>"
        lines.append(line)
    return "\n\n".join(lines)
