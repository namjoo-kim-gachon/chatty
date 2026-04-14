from __future__ import annotations

import redis.asyncio as aioredis

from app.config import settings

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    if _redis is None:
        msg = "Redis not initialized"
        raise RuntimeError(msg)
    return _redis


async def init_redis() -> None:
    global _redis  # noqa: PLW0603
    _redis = aioredis.from_url(settings.redis_url, decode_responses=True)


async def close_redis() -> None:
    global _redis  # noqa: PLW0603
    if _redis is not None:
        await _redis.aclose()
        _redis = None
