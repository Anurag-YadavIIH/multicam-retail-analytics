"""Shared Redis client - backs the live-preview frame cache (frame:latest:{camera_id})."""

import redis

from backend.app.core.config import get_settings


def _client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url)


redis_client = _client()


def get_redis() -> redis.Redis:
    return redis_client
