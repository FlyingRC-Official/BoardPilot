from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Callable
from secrets import compare_digest
import time
from typing import Literal, Optional

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

from app.core.config import settings

Role = Literal["admin", "support", "maintainer", "reviewer", "evaluator", "viewer"]
ROLES = {"admin", "support", "maintainer", "reviewer", "evaluator", "viewer"}


class CurrentUser(BaseModel):
    user_id: str
    role: Role


class SessionCreate(BaseModel):
    user_id: str
    role: Role
    ttl_seconds: Optional[int] = None


class SessionToken(BaseModel):
    session_token: str
    user: CurrentUser
    expires_at: int


def _session_signing_key() -> bytes:
    return (settings.api_key or "boardpilot-local-session-dev-key").encode("utf-8")


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def issue_session_token(user_id: str, role: Role, ttl_seconds: Optional[int] = None) -> SessionToken:
    ttl = ttl_seconds if ttl_seconds is not None else settings.session_ttl_seconds
    expires_at = int(time.time()) + max(int(ttl), 1)
    payload = {"user_id": user_id, "role": role, "exp": expires_at}
    payload_part = _b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_session_signing_key(), payload_part.encode("ascii"), hashlib.sha256).hexdigest()
    user = CurrentUser(user_id=user_id, role=role)
    return SessionToken(session_token=f"{payload_part}.{signature}", user=user, expires_at=expires_at)


def validate_session_token(token: str) -> CurrentUser:
    try:
        payload_part, signature = token.split(".", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid session")
    expected = hmac.new(_session_signing_key(), payload_part.encode("ascii"), hashlib.sha256).hexdigest()
    if not compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="invalid session")
    try:
        payload = json.loads(_b64decode(payload_part).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="invalid session")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=401, detail="session expired")
    role = payload.get("role")
    if role not in ROLES:
        raise HTTPException(status_code=401, detail="invalid session")
    return CurrentUser(user_id=str(payload.get("user_id", "")), role=role)


def get_current_user(
    x_boardpilot_user: str = Header("local", alias="X-BoardPilot-User"),
    x_boardpilot_role: Role = Header("admin", alias="X-BoardPilot-Role"),
    x_boardpilot_api_key: str = Header("", alias="X-BoardPilot-API-Key"),
    x_boardpilot_session: str = Header("", alias="X-BoardPilot-Session"),
) -> CurrentUser:
    if x_boardpilot_session:
        return validate_session_token(x_boardpilot_session)
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
