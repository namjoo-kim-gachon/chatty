from __future__ import annotations

import json
import time
from dataclasses import dataclass
from uuid import UUID

from app.database import Row, get_db_context
from app.redis_client import get_redis

# ---------------------------------------------------------------------------
# TTLs (seconds)
# ---------------------------------------------------------------------------
_ROOM_TTL: int = 600
_MOD_TTL: int = 600
_USER_TTL: int = 600

# ---------------------------------------------------------------------------
# Public data types (used by callers)
# ---------------------------------------------------------------------------


@dataclass
class RoomMeta:
    room_id: str
    is_private: bool
    deleted_at: float | None
    slow_mode_sec: int
    room_type: str
    game_server_url: str | None

    def is_deleted(self) -> bool:
        return self.deleted_at is not None


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _dump(obj: object) -> str:
    def _default(o: object) -> object:
        if isinstance(o, UUID):
            return str(o)
        msg = f"Not serializable: {type(o)}"
        raise TypeError(msg)

    return json.dumps(obj, default=_default)


def _row_to_dict(row: Row) -> dict[str, object]:
    result: dict[str, object] = {}
    for k, v in row.items():
        if isinstance(v, UUID):
            result[k] = str(v)
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# Room metadata
# ---------------------------------------------------------------------------


async def get_room_row(room_id: str) -> Row | None:
    r = get_redis()
    raw = await r.get(f"chatty:room_row:{room_id}")
    if raw is not None:
        return json.loads(raw)  # type: ignore[return-value]

    async with get_db_context() as db:
        cur = await db.execute("SELECT * FROM rooms WHERE id = %s", (room_id,))
        row = await cur.fetchone()
    if row is not None:
        await r.set(
            f"chatty:room_row:{room_id}", _dump(_row_to_dict(row)), ex=_ROOM_TTL
        )
    return row


async def get_room(room_id: str) -> RoomMeta | None:
    r = get_redis()
    raw = await r.get(f"chatty:room:{room_id}")
    if raw is not None:
        d = json.loads(raw)
        return RoomMeta(
            room_id=str(d["room_id"]),
            is_private=bool(d["is_private"]),
            deleted_at=float(d["deleted_at"]) if d["deleted_at"] is not None else None,
            slow_mode_sec=int(d["slow_mode_sec"]),
            room_type=str(d["room_type"]),
            game_server_url=(
                str(d["game_server_url"]) if d["game_server_url"] is not None else None
            ),
        )

    row = await get_room_row(room_id)
    if row is None:
        return None

    meta = RoomMeta(
        room_id=room_id,
        is_private=bool(row["is_private"]),
        deleted_at=float(row["deleted_at"]) if row["deleted_at"] is not None else None,
        slow_mode_sec=int(row["slow_mode_sec"]),  # type: ignore[arg-type]
        room_type=str(row["type"]),
        game_server_url=(
            str(row["game_server_url"]) if row["game_server_url"] is not None else None
        ),
    )
    await r.set(
        f"chatty:room:{room_id}",
        _dump(
            {
                "room_id": meta.room_id,
                "is_private": meta.is_private,
                "deleted_at": meta.deleted_at,
                "slow_mode_sec": meta.slow_mode_sec,
                "room_type": meta.room_type,
                "game_server_url": meta.game_server_url,
            }
        ),
        ex=_ROOM_TTL,
    )
    return meta


async def get_all_rooms() -> list[Row]:
    r = get_redis()
    raw = await r.get("chatty:room_list")
    if raw is not None:
        return json.loads(raw)  # type: ignore[return-value]

    async with get_db_context() as db:
        cur = await db.execute(
            "SELECT * FROM rooms WHERE deleted_at IS NULL AND is_dm = FALSE"
        )
        rows = await cur.fetchall()
    serializable = [_row_to_dict(row) for row in rows]
    await r.set("chatty:room_list", _dump(serializable), ex=_ROOM_TTL)
    return rows


async def invalidate_room_list() -> None:
    await get_redis().delete("chatty:room_list")


async def invalidate_room(room_id: str) -> None:
    r = get_redis()
    pipe = r.pipeline()
    pipe.delete(
        f"chatty:room:{room_id}",
        f"chatty:room_row:{room_id}",
        f"chatty:room_tags:{room_id}",
        f"chatty:room_attrs:{room_id}",
        f"chatty:rfilters:{room_id}",
        "chatty:room_list",
    )
    await pipe.execute()
    # Purge compound per-user keys for this room (rare -- room deletion/update)
    for pattern in (
        f"chatty:rban:{room_id}:*",
        f"chatty:mute:{room_id}:*",
        f"chatty:room_member:{room_id}:*",
        f"chatty:slow:{room_id}:*",
    ):
        keys: list[str] = []
        async for key in r.scan_iter(pattern):  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            keys.append(key)  # pyright: ignore[reportUnknownArgumentType]
        if keys:
            await r.delete(*keys)


# ---------------------------------------------------------------------------
# User cache
# ---------------------------------------------------------------------------


async def _cache_user(row: Row) -> None:
    r = get_redis()
    uid = str(row["id"])
    d = _row_to_dict(row)
    pipe = r.pipeline()
    pipe.set(f"chatty:user:{uid}", _dump(d), ex=_USER_TTL)
    pipe.set(f"chatty:email:{row['email']}", uid, ex=_USER_TTL)
    pipe.set(f"chatty:nick:{row['nickname']}", uid, ex=_USER_TTL)
    await pipe.execute()


async def get_user(user_id: str) -> Row | None:
    r = get_redis()
    raw = await r.get(f"chatty:user:{user_id}")
    if raw is not None:
        return json.loads(raw)  # type: ignore[return-value]

    async with get_db_context() as db:
        cur = await db.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        row = await cur.fetchone()
    if row is not None:
        await _cache_user(row)
    return row


async def get_user_by_email(email: str) -> Row | None:
    r = get_redis()
    uid = await r.get(f"chatty:email:{email}")
    if uid is not None:
        raw = await r.get(f"chatty:user:{uid}")
        if raw is not None:
            return json.loads(raw)  # type: ignore[return-value]

    async with get_db_context() as db:
        cur = await db.execute("SELECT * FROM users WHERE email = %s", (email,))
        row = await cur.fetchone()
    if row is not None:
        await _cache_user(row)
    return row


async def get_user_by_nickname(nickname: str) -> Row | None:
    r = get_redis()
    uid = await r.get(f"chatty:nick:{nickname}")
    if uid is not None:
        raw = await r.get(f"chatty:user:{uid}")
        if raw is not None:
            return json.loads(raw)  # type: ignore[return-value]

    async with get_db_context() as db:
        cur = await db.execute("SELECT * FROM users WHERE nickname = %s", (nickname,))
        row = await cur.fetchone()
    if row is not None:
        await _cache_user(row)
    return row


async def get_users_batch(user_ids: list[str]) -> list[Row]:
    if not user_ids:
        return []
    r = get_redis()
    keys = [f"chatty:user:{uid}" for uid in user_ids]
    values = await r.mget(keys)
    result: dict[str, Row] = {}
    missing: list[str] = []
    for uid, raw in zip(user_ids, values, strict=False):
        if raw is not None:
            result[uid] = json.loads(raw)
        else:
            missing.append(uid)
    if missing:
        async with get_db_context() as db:
            from typing import LiteralString, cast

            from psycopg import sql as pgsql

            ph = ",".join(["%s"] * len(missing))
            cur = await db.execute(
                pgsql.SQL(
                    cast("LiteralString", f"SELECT * FROM users WHERE id IN ({ph})")  # noqa: S608
                ),
                missing,
            )
            for row in await cur.fetchall():
                uid = str(row["id"])
                await _cache_user(row)
                result[uid] = row
    return [result[uid] for uid in user_ids if uid in result]


async def cache_user(row: Row) -> None:
    """Explicitly populate user cache (e.g. after INSERT)."""
    await _cache_user(row)


async def invalidate_user(user_id: str) -> None:
    r = get_redis()
    raw = await r.get(f"chatty:user:{user_id}")
    pipe = r.pipeline()
    if raw is not None:
        d = json.loads(raw)
        pipe.delete(f"chatty:email:{d['email']}")
        pipe.delete(f"chatty:nick:{d['nickname']}")
    pipe.delete(f"chatty:user:{user_id}")
    await pipe.execute()


# ---------------------------------------------------------------------------
# Room tags / attrs
# ---------------------------------------------------------------------------


async def get_room_tags(room_id: str) -> list[str]:
    r = get_redis()
    raw = await r.get(f"chatty:room_tags:{room_id}")
    if raw is not None:
        return json.loads(raw)  # type: ignore[return-value]

    async with get_db_context() as db:
        cur = await db.execute(
            "SELECT tag FROM room_tags WHERE room_id = %s", (room_id,)
        )
        rows = await cur.fetchall()
    tags = [str(row["tag"]) for row in rows]
    await r.set(f"chatty:room_tags:{room_id}", _dump(tags), ex=_ROOM_TTL)
    return tags


async def get_room_attrs(room_id: str) -> dict[str, str]:
    r = get_redis()
    raw = await r.get(f"chatty:room_attrs:{room_id}")
    if raw is not None:
        return json.loads(raw)  # type: ignore[return-value]

    async with get_db_context() as db:
        cur = await db.execute(
            "SELECT key, value FROM room_attrs WHERE room_id = %s", (room_id,)
        )
        rows = await cur.fetchall()
    attrs = {str(row["key"]): str(row["value"]) for row in rows}
    await r.set(f"chatty:room_attrs:{room_id}", _dump(attrs), ex=_ROOM_TTL)
    return attrs


async def invalidate_room_tags(room_id: str) -> None:
    await get_redis().delete(f"chatty:room_tags:{room_id}")


async def invalidate_room_attrs(room_id: str) -> None:
    await get_redis().delete(f"chatty:room_attrs:{room_id}")


# ---------------------------------------------------------------------------
# Room membership
# ---------------------------------------------------------------------------


async def check_room_member(room_id: str, user_id: str) -> bool:
    r = get_redis()
    raw = await r.get(f"chatty:room_member:{room_id}:{user_id}")
    if raw is not None:
        return raw == "1"

    async with get_db_context() as db:
        cur = await db.execute(
            "SELECT 1 FROM room_members WHERE room_id = %s AND user_id = %s",
            (room_id, user_id),
        )
        row = await cur.fetchone()
    is_member = row is not None
    value = "1" if is_member else "0"
    await r.set(f"chatty:room_member:{room_id}:{user_id}", value, ex=_ROOM_TTL)
    return is_member


async def invalidate_room_member(room_id: str, user_id: str) -> None:
    await get_redis().delete(f"chatty:room_member:{room_id}:{user_id}")


# ---------------------------------------------------------------------------
# Ban / mute
# ---------------------------------------------------------------------------


def _mod_currently_active(d: object, now: float) -> bool:
    if not isinstance(d, dict):
        return False
    if not d.get("is_active"):  # pyright: ignore[reportUnknownMemberType]
        return False
    expires_at = d.get("expires_at")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if expires_at is None:
        return True
    return now < float(expires_at)  # pyright: ignore[reportUnknownArgumentType]


async def check_room_moderation(user_id: str, room_id: str) -> tuple[bool, bool]:
    """Return (room_banned, room_muted). Cache-first."""
    now = time.time()
    r = get_redis()

    rban_raw, mute_raw = await r.mget(
        f"chatty:rban:{room_id}:{user_id}",
        f"chatty:mute:{room_id}:{user_id}",
    )

    if rban_raw is None or mute_raw is None:
        async with get_db_context() as db:
            if rban_raw is None:
                cur = await db.execute(
                    "SELECT expires_at FROM room_bans"
                    " WHERE room_id = %s AND user_id = %s"
                    " AND (expires_at IS NULL OR expires_at > %s) LIMIT 1",
                    (room_id, user_id, now),
                )
                row = await cur.fetchone()
                rban_dict: dict[str, object] = {
                    "is_active": row is not None,
                    "expires_at": float(row["expires_at"])
                    if row is not None and row["expires_at"] is not None
                    else None,
                }
                rban_raw = _dump(rban_dict)
                await r.set(f"chatty:rban:{room_id}:{user_id}", rban_raw, ex=_MOD_TTL)

            if mute_raw is None:
                cur = await db.execute(
                    "SELECT expires_at FROM room_mutes"
                    " WHERE room_id = %s AND user_id = %s"
                    " AND (expires_at IS NULL OR expires_at > %s) LIMIT 1",
                    (room_id, user_id, now),
                )
                row = await cur.fetchone()
                mute_dict: dict[str, object] = {
                    "is_active": row is not None,
                    "expires_at": float(row["expires_at"])
                    if row is not None and row["expires_at"] is not None
                    else None,
                }
                mute_raw = _dump(mute_dict)
                await r.set(f"chatty:mute:{room_id}:{user_id}", mute_raw, ex=_MOD_TTL)

    return (
        _mod_currently_active(json.loads(rban_raw), now),
        _mod_currently_active(json.loads(mute_raw), now),
    )


async def set_muted(room_id: str, user_id: str, expires_at: float) -> None:
    """Immediately write mute into cache (called by spam detector after auto-mute)."""
    await get_redis().set(
        f"chatty:mute:{room_id}:{user_id}",
        _dump({"is_active": True, "expires_at": expires_at}),
        ex=_MOD_TTL,
    )


async def invalidate_global_ban(user_id: str) -> None:
    await get_redis().delete(f"chatty:gban:{user_id}")


async def invalidate_room_ban(room_id: str, user_id: str) -> None:
    await get_redis().delete(f"chatty:rban:{room_id}:{user_id}")


async def invalidate_room_mute(room_id: str, user_id: str) -> None:
    await get_redis().delete(f"chatty:mute:{room_id}:{user_id}")


# ---------------------------------------------------------------------------
# Slow mode -- last message time
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Slow mode -- last message time
# ---------------------------------------------------------------------------


async def get_last_msg_at(room_id: str, user_id: str) -> float | None:
    raw = await get_redis().get(f"chatty:slow:{room_id}:{user_id}")
    return float(raw) if raw is not None else None


async def update_last_msg_at(room_id: str, user_id: str, ts: float) -> None:
    await get_redis().set(f"chatty:slow:{room_id}:{user_id}", str(ts))
