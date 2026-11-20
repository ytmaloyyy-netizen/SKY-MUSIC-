from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _parse_int(value: str | None, default: int = 0) -> int:
    if not value:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_timezone(tz_name: str | None) -> ZoneInfo:
    candidate = (tz_name or "Europe/Moscow").strip()
    try:
        return ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


@dataclass(frozen=True)
class Config:
    bot_token: str
    developer_id: int
    timezone_name: str
    tz: ZoneInfo
    database_path: Path
    temp_dir: Path
    logs_dir: Path
    data_dir: Path
    max_file_size_mb: int
    default_daily_limit: int
    maintenance_mode: bool
    registration_open: bool
    worker_concurrency: int

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def is_developer_configured(self) -> bool:
        return self.developer_id > 0


def load_config() -> Config:
    token = (os.getenv("BOT_TOKEN") or "").strip()
    dev_id = _parse_int(os.getenv("DEVELOPER_ID"), default=0)
    tz_name = (os.getenv("TIMEZONE") or "Europe/Moscow").strip()
    tz = _load_timezone(tz_name)

    data_dir = BASE_DIR / "data"
    temp_dir = BASE_DIR / (os.getenv("TEMP_DIR") or "temp")
    logs_dir = BASE_DIR / (os.getenv("LOGS_DIR") or "logs")
    db_raw = os.getenv("DATABASE_PATH") or "data/sky_music.db"
    database_path = BASE_DIR / db_raw if not os.path.isabs(db_raw) else Path(db_raw)

    data_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    return Config(
        bot_token=token,
        developer_id=dev_id,
        timezone_name=tz_name,
        tz=tz,
        database_path=database_path,
        temp_dir=temp_dir,
        logs_dir=logs_dir,
        data_dir=data_dir,
        max_file_size_mb=max(1, _parse_int(os.getenv("MAX_FILE_SIZE_MB"), default=50)),
        default_daily_limit=max(1, _parse_int(os.getenv("DEFAULT_DAILY_LIMIT"), default=5)),
        maintenance_mode=_parse_bool(os.getenv("MAINTENANCE_MODE"), default=False),
        registration_open=_parse_bool(os.getenv("REGISTRATION_OPEN"), default=True),
        worker_concurrency=max(1, _parse_int(os.getenv("WORKER_CONCURRENCY"), default=2)),
    )


config = load_config()
