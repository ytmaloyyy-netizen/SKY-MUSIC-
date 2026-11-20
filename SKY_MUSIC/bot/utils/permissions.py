from __future__ import annotations

from enum import StrEnum
from config import config


class Role(StrEnum):
    DEFAULT = "DEFAULT"
    PREMIUM = "PREMIUM"
    ADMIN = "ADMIN"
    DEVELOPER = "DEVELOPER"


ROLE_LABELS: dict[Role, str] = {
    Role.DEFAULT: "🎧 DEFAULT",
    Role.PREMIUM: "🌟 PREMIUM",
    Role.ADMIN: "🛑 ADMIN",
    Role.DEVELOPER: "🧑‍💻 DEVELOPER 🚀",
}


def resolve_effective_role(user_id: int, stored_role: str | None) -> Role:
    if config.is_developer_configured and user_id == config.developer_id:
        return Role.DEVELOPER
    if stored_role == Role.DEVELOPER:
        # Никто кроме DEVELOPER_ID не может владеть ролью DEVELOPER
        return Role.DEFAULT
    try:
        role = Role(stored_role or Role.DEFAULT)
    except ValueError:
        role = Role.DEFAULT
    return role


def is_developer(user_id: int, role: Role | str | None = None) -> bool:
    if config.is_developer_configured and user_id == config.developer_id:
        return True
    if isinstance(role, Role):
        return role == Role.DEVELOPER
    return False


def is_admin_or_above(user_id: int, role: Role | str | None = None) -> bool:
    if is_developer(user_id, role):
        return True
    effective = role if isinstance(role, Role) else resolve_effective_role(user_id, str(role) if role else None)
    return effective in {Role.ADMIN, Role.DEVELOPER}


def can_use_spatial_audio(user_id: int, role: Role | str | None = None) -> bool:
    return is_admin_or_above(user_id, role)


def has_unlimited_quota(user_id: int, role: Role | str | None = None, custom_unlimited: bool = False) -> bool:
    if custom_unlimited or is_admin_or_above(user_id, role):
        return True
    effective = role if isinstance(role, Role) else resolve_effective_role(user_id, str(role) if role else None)
    return effective == Role.PREMIUM
