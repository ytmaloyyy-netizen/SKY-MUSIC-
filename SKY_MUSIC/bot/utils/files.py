from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from config import config

ALLOWED_AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".ogg", ".oga", ".m4a", ".aac", ".flac", ".opus", ".wma"
}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}


def create_job_dir(user_id: int) -> Path:
    job_id = f"{user_id}_{uuid.uuid4().hex}"
    path = config.temp_dir / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_job_dir(path: Path | None) -> None:
    if path and path.exists() and path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def sanitize_filename(name: str | None, fallback: str = "audio_track.mp3") -> str:
    if not name:
        return fallback
    cleaned = Path(name).name.replace("\x00", "")
    for ch in ("/", "\\", "..", ":", "*", "?", '"', "<", ">", "|"):
        cleaned = cleaned.replace(ch, "_")
    return cleaned.strip() or fallback
