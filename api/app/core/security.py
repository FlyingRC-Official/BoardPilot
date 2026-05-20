from collections.abc import Callable
from typing import Literal

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

Role = Literal["admin", "support", "reviewer", "viewer"]


class CurrentUser(BaseModel):
    user_id: str
    role: Role


def get_current_user(
    x_boardpilot_user: str = Header("local", alias="X-BoardPilot-User"),
    x_boardpilot_role: Role = Header("admin", alias="X-BoardPilot-Role"),
) -> CurrentUser:
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
