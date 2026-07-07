import pytest

from backend.app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_roundtrip():
    hashed = hash_password("s3cret!")
    assert verify_password("s3cret!", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_contains_role():
    token = create_access_token("42", "manager")
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "manager"
    assert payload["type"] == "access"


def test_refresh_token_type():
    payload = decode_token(create_refresh_token("7"))
    assert payload["type"] == "refresh"


def test_tampered_token_rejected():
    import jwt

    token = create_access_token("1", "admin") + "x"
    with pytest.raises(jwt.PyJWTError):
        decode_token(token)
