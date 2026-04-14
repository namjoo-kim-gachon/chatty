from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.redis_client import get_redis


class RedisRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def is_allowed(self, key: str) -> bool:
        redis = get_redis()
        now = time.time()
        window_start = now - self.window_seconds
        redis_key = f"chatty:rl:{key}"
        member = f"{now}:{uuid.uuid4().hex}"

        pipe = redis.pipeline(transaction=True)
        pipe.zremrangebyscore(redis_key, "-inf", window_start)
        pipe.zadd(redis_key, {member: now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, self.window_seconds + 1)
        results: list[object] = await pipe.execute()

        count_raw = results[2]
        count = count_raw if isinstance(count_raw, int) else 0
        if count > self.max_requests:
            await redis.zrem(redis_key, member)
            return False
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, limiter: RedisRateLimiter) -> None:
        super().__init__(app)
        self.limiter = limiter

    async def dispatch(  # pyright: ignore[reportImplicitOverride]
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host
        else:
            client_ip = "unknown"

        if not await self.limiter.is_allowed(client_ip):
            return Response(
                content='{"detail":"Too many requests"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(self.limiter.window_seconds)},
            )
        return await call_next(request)
