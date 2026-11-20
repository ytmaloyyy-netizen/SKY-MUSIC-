from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from config import config
from bot.database.database import db
from bot.utils.permissions import Role, resolve_effective_role, has_unlimited_quota


def _now_dt() -> datetime:
    return datetime.now(config.tz)


def _today_str() -> str:
    return _now_dt().strftime("%Y-%m-%d")


async def get_setting(key: str, default: str = "") -> str:
    cursor = await db.conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = await cursor.fetchone()
    return str(row["value"]) if row else default


async def set_setting(key: str, value: str, actor_id: int | None = None) -> None:
    now_iso = _now_dt().isoformat()
    await db.conn.execute(
        """
        INSERT INTO settings (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, str(value), now_iso),
    )
    if actor_id is not None:
        await log_admin_action(
            actor_id=actor_id,
            action_type="UPDATE_SETTING",
            target_user_id=None,
            details=f"{key}={value}",
        )
    await db.conn.commit()


async def log_admin_action(
    actor_id: int,
    action_type: str,
    target_user_id: int | None = None,
    details: str | None = None,
) -> None:
    now_iso = _now_dt().isoformat()
    await db.conn.execute(
        """
        INSERT INTO admin_logs (actor_id, action_type, target_user_id, details, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (actor_id, action_type, target_user_id, details, now_iso),
    )
    await db.conn.commit()


async def get_user(user_id: int) -> dict[str, Any] | None:
    cursor = await db.conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    if not row:
        return None
    data = dict(row)
    data["effective_role"] = resolve_effective_role(user_id, data.get("role"))
    return data


async def upsert_user(
    user_id: int,
    username: str | None,
    full_name: str | None,
    allow_registration: bool = True,
) -> tuple[dict[str, Any] | None, bool]:
    """Возвращает (user_dict, is_new_user). Если регистрация закрыта для нового юзера — (None, False)."""
    existing = await get_user(user_id)
    now_iso = _now_dt().isoformat()
    today = _today_str()
    default_limit = int(await get_setting("default_daily_limit", str(config.default_daily_limit)))

    if existing:
        effective_role = resolve_effective_role(user_id, existing.get("role"))
        stored_role = Role.DEVELOPER.value if effective_role == Role.DEVELOPER else effective_role.value
        await db.conn.execute(
            """
            UPDATE users
            SET username = ?, full_name = ?, role = ?, last_active_at = ?
            WHERE user_id = ?
            """,
            (username, full_name, stored_role, now_iso, user_id),
        )
        await db.conn.execute(
            """
            INSERT INTO usage_limits (user_id, limit_date, used_today, bonus_credits, updated_at)
            VALUES (?, ?, 0, 0, ?)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id, today, now_iso),
        )
        await db.conn.commit()
        return await get_user(user_id), False

    if not allow_registration and not (config.is_developer_configured and user_id == config.developer_id):
        return None, False

    initial_role = (
        Role.DEVELOPER.value
        if (config.is_developer_configured and user_id == config.developer_id)
        else Role.DEFAULT.value
    )
    eff_limit = None if initial_role == Role.DEVELOPER.value else default_limit

    await db.conn.execute(
        """
        INSERT INTO users (
            user_id, username, full_name, role, is_banned, ban_reason,
            total_processed, custom_daily_limit, unlimited_quota, registered_at, last_active_at
        ) VALUES (?, ?, ?, ?, 0, NULL, 0, ?, ?, ?, ?)
        """,
        (
            user_id,
            username,
            full_name,
            initial_role,
            eff_limit,
            1 if initial_role == Role.DEVELOPER.value else 0,
            now_iso,
            now_iso,
        ),
    )
    await db.conn.execute(
        """
        INSERT INTO roles (user_id, role_name, assigned_by, assigned_at, is_active)
        VALUES (?, ?, ?, ?, 1)
        """,
        (user_id, initial_role, None, now_iso),
    )
    await db.conn.execute(
        """
        INSERT INTO usage_limits (user_id, limit_date, used_today, bonus_credits, updated_at)
        VALUES (?, ?, 0, 0, ?)
        """,
        (user_id, today, now_iso),
    )
    await db.conn.commit()
    return await get_user(user_id), True


async def sync_daily_quota(user_id: int) -> dict[str, Any]:
    """Сбрасывает used_today при наступлении новых суток по config.tz."""
    today = _today_str()
    now_iso = _now_dt().isoformat()
    cursor = await db.conn.execute("SELECT * FROM usage_limits WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    if not row:
        await db.conn.execute(
            """
            INSERT INTO usage_limits (user_id, limit_date, used_today, bonus_credits, updated_at)
            VALUES (?, ?, 0, 0, ?)
            """,
            (user_id, today, now_iso),
        )
        await db.conn.commit()
        return {"user_id": user_id, "limit_date": today, "used_today": 0, "bonus_credits": 0}

    data = dict(row)
    if data["limit_date"] != today:
        await db.conn.execute(
            """
            UPDATE usage_limits
            SET limit_date = ?, used_today = 0, updated_at = ?
            WHERE user_id = ?
            """,
            (today, now_iso, user_id),
        )
        await db.conn.commit()
        data["limit_date"] = today
        data["used_today"] = 0
    return data


async def get_quota_status(user: dict[str, Any]) -> dict[str, Any]:
    user_id = int(user["user_id"])
    role: Role = user["effective_role"]
    custom_unlimited = bool(user.get("unlimited_quota"))
    limit_row = await sync_daily_quota(user_id)

    if has_unlimited_quota(user_id, role, custom_unlimited):
        return {
            "unlimited": True,
            "used": int(limit_row["used_today"]),
            "total": None,
            "remaining": None,
            "bonus": int(limit_row["bonus_credits"]),
        }

    default_limit = int(await get_setting("default_daily_limit", str(config.default_daily_limit)))
    base_limit = user.get("custom_daily_limit")
    daily_cap = int(base_limit) if base_limit is not None else default_limit
    bonus = int(limit_row["bonus_credits"])
    total_available = max(0, daily_cap + bonus)
    used = int(limit_row["used_today"])
    remaining = max(0, total_available - used)

    return {
        "unlimited": False,
        "used": used,
        "total": total_available,
        "remaining": remaining,
        "bonus": bonus,
    }


async def consume_processing_quota(user: dict[str, Any]) -> bool:
    """Атомарно списывает 1 обработку, если лимит позволяет."""
    user_id = int(user["user_id"])
    role: Role = user["effective_role"]
    custom_unlimited = bool(user.get("unlimited_quota"))
    now_iso = _now_dt().isoformat()
    await sync_daily_quota(user_id)

    if has_unlimited_quota(user_id, role, custom_unlimited):
        await db.conn.execute(
            """
            UPDATE usage_limits
            SET used_today = used_today + 1, updated_at = ?
            WHERE user_id = ?
            """,
            (now_iso, user_id),
        )
        await db.conn.execute(
            "UPDATE users SET total_processed = total_processed + 1 WHERE user_id = ?",
            (user_id,),
        )
        await db.conn.commit()
        return True

    status = await get_quota_status(user)
    if status["remaining"] is None or status["remaining"] <= 0:
        return False

    await db.conn.execute(
        """
        UPDATE usage_limits
        SET used_today = used_today + 1, updated_at = ?
        WHERE user_id = ?
        """,
        (now_iso, user_id),
    )
    await db.conn.execute(
        "UPDATE users SET total_processed = total_processed + 1 WHERE user_id = ?",
        (user_id,),
    )
    await db.conn.commit()
    return True


async def assign_role(
    target_user_id: int,
    new_role: Role,
    actor_id: int,
    premium_days: int | None = None,
) -> tuple[bool, str]:
    # Защита: роль DEVELOPER нельзя выдать или снять через обычные действия
    if new_role == Role.DEVELOPER:
        return False, "Роль DEVELOPER жёстко закреплена в конфигурации и не может назначаться через панель."

    target = await get_user(target_user_id)
    if not target:
        return False, "Пользователь не найден в базе данных."

    if target["effective_role"] == Role.DEVELOPER:
        return False, "Нельзя изменять или снимать роль DEVELOPER."

    now = _now
