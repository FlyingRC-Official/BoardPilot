from collections.abc import Callable
from secrets import compare_digest
from typing import Literal

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from app.core.config import settings

Role = Literal["admin", "support", "reviewer", "viewer"]


class CurrentUser(BaseModel):
    user_id: str
    role: Role


def get_current_user(
    x_boardpilot_user: str = Header("local", alias="X-BoardPilot-User"),
    x_boardpilot_role: Role = Header("admin", alias="X-BoardPilot-Role"),
    x_boardpilot_api_key: str = Header("", alias="X-BoardPilot-API-Key"),
) -> CurrentUser:
    if settings.api_key and not compare_digest(x_boardpilot_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="invalid API key")
    return CurrentUser(user_id=x_boardpilot_user, role=x_boardpilot_role)


def require_roles(*roles: Role) -> Callable[[CurrentUser], CurrentUser]:
    def dependency(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        return assert_role(user, *roles)

    return dependency


def assert_role(user: CurrentUser, *roles: Role) -> CurrentUser:
    if user.role not in roles:
        raise HTTPException(status_code=403, detail=f"requires one of roles: {', '.join(roles)}")
    return user
