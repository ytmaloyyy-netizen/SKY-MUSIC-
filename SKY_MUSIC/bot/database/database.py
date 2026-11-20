from __future__ import annotations

from datetime import datetime
from pathlib import Path
import aiosqlite
from config import config
from bot.database.models import SCHEMA_SQL


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA_SQL)
        await self._seed_default_settings()
        await self._conn.commit()

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("База данных не подключена. Сначала вызовите await db.connect().")
        return self._conn

    async def _seed_default_settings(self) -> None:
        now_iso = datetime.now(config.tz).isoformat()
        defaults = {
            "maintenance_mode": "1" if config.maintenance_mode else "0",
            "registration_open": "1" if config.registration_open else "0",
            "default_daily_limit": str(config.default_daily_limit),
            "default_premium_days": "30",
            "worker_concurrency": str(config.worker_concurrency),
        }
        for key, value in defaults.items():
            await self.conn.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO NOTHING
                """,
                (key, value, now_iso),
            )

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None


db = Database(config.database_path)
