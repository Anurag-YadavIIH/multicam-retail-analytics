"""Shared fixtures. API tests run against SQLite - no Postgres/torch needed."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-0123456789ab")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core import database
from backend.app.core.database import Base, get_db
from backend.app.core.redis_client import get_redis
from backend.app.core.security import hash_password
from backend.app.models import Role, User


class FakeRedis:
    """In-memory stand-in for the redis.Redis client used by the preview endpoints."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    def get(self, key: str) -> bytes | None:
        return self.store.get(key)

    def set(self, key: str, value: bytes, ex: int | None = None) -> None:
        self.store[key] = value


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    session = testing_session()
    # celery tasks import SessionLocal directly - point it at the test engine
    database.SessionLocal = testing_session
    yield session
    session.close()


@pytest.fixture()
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture()
def client(db_session, fake_redis):
    from backend.app.main import app

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: fake_redis
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_user(db, email="admin@test.local", password="secret123", role=Role.admin) -> User:
    user = User(email=email, hashed_password=hash_password(password), role=role, full_name="T")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def admin_token(client, db_session) -> str:
    make_user(db_session)
    resp = client.post(
        "/api/v1/auth/login", data={"username": "admin@test.local", "password": "secret123"}
    )
    return resp.json()["access_token"]


@pytest.fixture()
def viewer_token(client, db_session) -> str:
    make_user(db_session, email="viewer@test.local", role=Role.viewer)
    resp = client.post(
        "/api/v1/auth/login", data={"username": "viewer@test.local", "password": "secret123"}
    )
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
