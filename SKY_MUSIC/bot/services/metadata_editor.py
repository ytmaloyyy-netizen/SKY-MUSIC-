from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, APIC, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Cover


@dataclass
class AudioMetadataTags:
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    year: str | None = None
    genre: str | None = None
    track_number: str | None = None
    comment: str | None = None
    clear_existing: bool = False


def _run_ffmpeg(args: list[str]) -> None:
    proc = subprocess.run(["ffmpeg", "-y", *args], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        err_tail = (proc.stderr or "").strip().splitlines()[-5:]
        raise RuntimeError(f"Ошибка FFmpeg: {' | '.join(err_tail)}")


def _detect_image_mime(cover_path: Path) -> str:
    ext = cover_path.suffix.lower()
    if ext in {".png"}:
        return "image/png"
    return "image/jpeg"


def _apply_metadata_sync(
    input_path: Path,
    output_path: Path,
    tags: AudioMetadataTags,
    cover_path: Path | None = None,
    target_ext: str | None = None,
) -> Path:
    ext = (target_ext or input_path.suffix or ".mp3").lower().lstrip(".")
    if ext not in {"mp3", "flac", "m4a"}:
        ext = "mp3"

    working_file = output_path.with_suffix(f".{ext}")

    # Конвертация при смене формата или приведении к нужному контейнеру
    if input_path.suffix.lower().lstrip(".") != ext:
        if ext == "mp3":
            _run_ffmpeg(["-i", str(input_path), "-vn", "-c:a", "libmp3lame", "-b:a", "320k", str(working_file)])
        elif ext == "flac":
            _run_ffmpeg(["-i", str(input_path), "-vn", "-c:a", "flac", str(working_file)])
        elif ext == "m4a":
            _run_ffmpeg(["-i", str(input_path), "-vn", "-c:a", "aac", "-b:a", "256k", str(working_file)])
    else:
        _run_ffmpeg(["-i", str(input_path), "-vn", "-c:a", "copy", str(working_file)])

    if ext == "mp3":
        try:
            audio_id3 = ID3(str(working_file))
        except ID3NoHeaderError:
            audio_id3 = ID3()

        if tags.clear_existing:
            audio_id3.clear()

        easy = EasyID3(str(working_file))
        if tags.clear_existing:
            easy.delete()
        if tags.title is not None:
            easy["title"] = [tags.title]
        if tags.artist is not None:
            easy["artist"] = [tags.artist]
        if tags.album is not None:
            easy["album"] = [tags.album]
        if tags.year is not None:
            easy["date"] = [tags.year]
        if tags.genre is not None:
            easy["genre"] = [tags.genre]
        if tags.track_number is not None:
            easy["tracknumber"] = [tags.track_number]
        easy.save(str(working_file))

        audio_id3 = ID3(str(working_file))
        if tags.comment is not None:
            from mutagen.id3 import COMM
            audio_id3.delall("COMM")
            audio_id3.add(COMM(encoding=3, lang="rus", desc="", text=tags.comment))

        if cover_path and cover_path.exists():
            mime = _detect_image_mime(cover_path)
            img_bytes = cover_path.read_bytes()
            audio_id3.delall("APIC")
            audio_id3.add(
                APIC(
                    encoding=3,
                    mime=mime,
                    type=3,
                    desc="Cover",
                    data=img_bytes,
                )
            )
        audio_id3.save(str(working_file))

    elif ext == "flac":
        flac_file = FLAC(str(working_file))
        if tags.clear_existing:
            flac_file.clear()
            flac_file.clear_pictures()
        if tags.title is not None:
            flac_file["title"] = [tags.title]
        if tags.artist is not None:
            flac_file["artist"] = [tags.artist]
        if tags.album is not None:
            flac_file["album"] = [tags.album]
        if tags.year is not None:
            flac_file["date"] = [tags.year]
        if tags.genre is not None:
            flac_file["genre"] = [tags.genre]
        if tags.track_number is not None:
            flac_file["tracknumber"] = [tags.track_number]
        if tags.comment is not None:
            flac_file["comment"] = [tags.comment]

        if cover_path and cover_path.exists():
            pic = Picture()
            pic.data = cover_path.read_bytes()
            pic.mime = _detect_image_mime(cover_path)
            pic.type = 3
            pic.desc = "Cover"
            flac_file.clear_pictures()
            flac_file.add_picture(pic)
        flac_file.save()

    elif ext == "m4a":
        mp4_file = MP4(str(working_file))
        if tags.clear_existing:
            mp4_file.clear()
        if tags.title is not None:
            mp4_file["\xa9nam"] = [tags.title]
        if tags.artist is not None:
            mp4_file["\xa9ART"] = [tags.artist]
        if tags.album is not None:
            mp4_file["\xa9alb"] = [tags.album]
        if tags.year is not None:
            mp4_file["\xa9day"] = [tags.year]
        if tags.genre is not None:
            mp4_file["\xa9gen"] = [tags.genre]
        if tags.comment is not None:
            mp4_file["\xa9cmt"] = [tags.comment]
        if tags.track_number is not None:
            try:
                t_num = int(tags.track_number.split("/")[0])
                mp4_file["trkn"] = [(t_num, 0)]
            except ValueError:
                pass

        if cover_path and cover_path.exists():
            img_bytes = cover_path.read_bytes()
            img_format = MP4Cover.FORMAT_PNG if cover_path.suffix.lower() == ".png" else MP4Cover.FORMAT_JPEG
            mp4_file["covr"] = [MP4Cover(img_bytes, imageformat=img_format)]
        mp4_file.save()

    return working_file


async def edit_audio_metadata(
    input_path: Path,
    output_path: Path,
    tags: AudioMetadataTags,
    cover_path: Path | None = None,
    target_ext: str | None = None,
) -> Path:
    return await asyncio.to_thread(
        _apply_metadata_sync,
        input_path,
        output_path,
        tags,
        cover_path,
        target_ext,
    )
