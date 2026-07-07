"""FastAPI dependencies: current user resolution and RBAC guards."""

from typing import Annotated

import jwt as pyjwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import decode_token
from backend.app.models.user import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
_optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _resolve_user(token: str | None, db: Session) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exc
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_exc
        user_id = int(payload["sub"])
    except (pyjwt.PyJWTError, KeyError, ValueError) as exc:
        raise credentials_exc from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exc
    return user


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    return _resolve_user(token, db)


def require_viewer_via_header_or_query(
    camera_id: int,
    token_header: Annotated[str | None, Depends(_optional_oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
    token: Annotated[str | None, Query()] = None,
) -> User | None:
    """Snapshot/stream auth: a normal JWT via the Authorization header (for
    direct API/curl use, checked exactly like get_current_user), or a
    short-lived camera-scoped token via ?token=... (for <img>/<video> src,
    which can't set headers). The query-param path deliberately does NOT
    accept a full access token - only a create_stream_token() token scoped to
    this exact camera_id, so a leaked/logged URL can't grant broader access."""
    if token_header:
        return _resolve_user(token_header, db)

    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exc
    try:
        payload = decode_token(token)
    except pyjwt.PyJWTError as exc:
        raise credentials_exc from exc
    if payload.get("type") != "stream" or payload.get("camera_id") != camera_id:
        raise credentials_exc
    return None


class RoleChecker:
    """RBAC guard. Role hierarchy: admin > manager > viewer."""

    _rank = {Role.viewer: 0, Role.manager: 1, Role.admin: 2}

    def __init__(self, minimum: Role):
        self.minimum = minimum

    def __call__(self, user: Annotated[User, Depends(get_current_user)]) -> User:
        if self._rank[user.role] < self._rank[self.minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role >= {self.minimum.value}",
            )
        return user


require_viewer = RoleChecker(Role.viewer)
require_manager = RoleChecker(Role.manager)
require_admin = RoleChecker(Role.admin)
