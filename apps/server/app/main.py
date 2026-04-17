from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.admin.router import router as admin_router
from app.auth.router import router as auth_router
from app.config import settings
from app.database import get_db_context, init_db, mark_user_active, mark_user_inactive
from app.message_writer import init_seqs
from app.message_writer import start as start_writer
from app.message_writer import stop as stop_writer
from app.messages.router import router as messages_router
from app.middleware.rate_limit import RateLimitMiddleware, RedisRateLimiter
from app.moderation.router import router as moderation_router
from app.redis_client import close_redis, init_redis
from app.rooms.router import router as rooms_router
from app.rooms.service import auto_delete_if_empty as _auto_delete
from app.sse import broadcaster
from app.users.router import router as users_router

logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    await init_redis()
    await init_db()
    loop = asyncio.get_running_loop()
    broadcaster.set_loop(loop)
    broadcaster.set_activity_callbacks(
        on_active=mark_user_active,
        on_inactive=mark_user_inactive,
    )

    async def _on_room_empty(room_id: str) -> None:
        # Grace period: brief SSE reconnects shouldn't delete the room
        await asyncio.sleep(60)
        await _auto_delete(room_id)

    broadcaster.set_room_empty_callback(on_room_empty=_on_room_empty)

    # Load room seq counters from DB, then start background writer thread.
    async with get_db_context() as conn:
        cur = await conn.execute("SELECT room_id, seq FROM room_seq")
        rows = await cur.fetchall()
    await init_seqs(rows)
    start_writer(settings.database_url)

    yield

    stop_writer()
    await close_redis()


app = FastAPI(
    title="Chatty",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
)

app.add_middleware(
    RateLimitMiddleware,
    limiter=RedisRateLimiter(
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    ),
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(rooms_router)
app.include_router(messages_router)
app.include_router(moderation_router)
app.include_router(admin_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
