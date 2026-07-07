"""JWT creation/validation and password hashing.

Uses pbkdf2_sha256 (pure python, no native deps) which keeps the docker
image slim and works identically on Windows/Linux/ARM.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.hash import pbkdf2_sha256

from backend.app.core.config import get_settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pbkdf2_sha256.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pbkdf2_sha256.verify(plain, hashed)
    except ValueError:
        return False


def _create_token(
    subject: str, token_type: str, expires_delta: timedelta, extra: dict[str, Any] | None = None
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(subject: str, role: str) -> str:
    settings = get_settings()
    return _create_token(
        subject,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
        {"role": role},
    )


def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    return _create_token(subject, "refresh", timedelta(days=settings.refresh_token_expire_days))


STREAM_TOKEN_TTL_S = 60


def create_stream_token(camera_id: int) -> str:
    """Short-lived, camera-scoped token for the live-preview <img>/<video> src -
    unlike an access token it grants nothing beyond snapshot/stream for this
    one camera_id, so it's safe to put in a URL."""
    return _create_token(
        str(camera_id), "stream", timedelta(seconds=STREAM_TOKEN_TTL_S), {"camera_id": camera_id}
    )


def decode_token(token: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError on invalid/expired tokens."""
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
