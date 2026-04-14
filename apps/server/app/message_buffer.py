"""
Per-room Redis-backed ring buffer for recent messages.

Caches the last MAX_MESSAGES messages per room so that initial loads
and SSE reconnect recovery can be served without hitting the database.
"""

from __future__ import annotations

from app.messages.schemas import MessageOut
from app.redis_client import get_redis

MAX_MESSAGES = 200

_BUF_KEY = "chatty:msgbuf:{}"
_WARM_KEY = "chatty:msgbuf_warm:{}"


async def append(room_id: str, msg: MessageOut) -> None:
    """Add a newly sent message to the buffer."""
    r = get_redis()
    buf_key = _BUF_KEY.format(room_id)
    warm_key = _WARM_KEY.format(room_id)
    pipe = r.pipeline()
    pipe.rpush(buf_key, msg.model_dump_json())
    pipe.ltrim(buf_key, -MAX_MESSAGES, -1)
    pipe.set(warm_key, "1")
    await pipe.execute()


async def warm(room_id: str, msgs: list[MessageOut]) -> None:
    """Seed buffer from DB results on first miss. No-op if already warmed."""
    r = get_redis()
    warm_key = _WARM_KEY.format(room_id)
    if await r.exists(warm_key):
        return
    buf_key = _BUF_KEY.format(room_id)
    pipe = r.pipeline()
    for msg in msgs:
        pipe.rpush(buf_key, msg.model_dump_json())
    if msgs:
        pipe.ltrim(buf_key, -MAX_MESSAGES, -1)
    pipe.set(warm_key, "1")
    await pipe.execute()


async def get_latest(room_id: str, limit: int) -> list[MessageOut] | None:
    """Return last `limit` messages, or None if buffer not warmed yet."""
    r = get_redis()
    if not await r.exists(_WARM_KEY.format(room_id)):
        return None
    raw_list: list[str] = await r.lrange(  # pyright: ignore[reportGeneralTypeIssues, reportUnknownMemberType, reportUnknownVariableType]
        _BUF_KEY.format(room_id), -limit, -1
    )
    return [MessageOut.model_validate_json(s) for s in raw_list]  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]


async def evict(room_id: str) -> None:
    """Remove buffer and warmed flag for a deleted room."""
    await get_redis().delete(_BUF_KEY.format(room_id), _WARM_KEY.format(room_id))


async def get_since_seq(
    room_id: str, since_seq: int, limit: int
) -> list[MessageOut] | None:
    """Return messages after since_seq, or None if buffer can't cover range."""
    r = get_redis()
    if not await r.exists(_WARM_KEY.format(room_id)):
        return None
    raw_list: list[str] = await r.lrange(  # pyright: ignore[reportGeneralTypeIssues, reportUnknownMemberType, reportUnknownVariableType]
        _BUF_KEY.format(room_id), 0, -1
    )
    if not raw_list:
        return []
    msgs = [MessageOut.model_validate_json(s) for s in raw_list]  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
    # Oldest buffered msg newer than since_seq means possible gap -- fall back to DB
    if msgs[0].seq > since_seq:
        return None
    result = [m for m in msgs if m.seq > since_seq]
    return result[:limit]
