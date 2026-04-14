from __future__ import annotations

import logging
import time
import uuid
from typing import LiteralString, cast

from fastapi import HTTPException, status

from app import message_buffer
from app.database import DBConn, Row
from app.game_relay import relay
from app.moderation import cache as mod_cache
from app.rooms.schemas import (
    OwnerTransfer,
    RoomCreate,
    RoomDetail,
    RoomJoin,
    RoomSummary,
    RoomUpdate,
)
from app.security import hash_password, verify_password
from app.sse import broadcaster
from app.users.schemas import UserOut

logger = logging.getLogger(__name__)

_SYSTEM_ROOM_MAX = 1000


async def get_owner_nickname(room: Row) -> str:
    user = await mod_cache.get_user(str(room["owner_id"]))
    return str(user["nickname"]) if user is not None else ""


async def row_to_room_detail(room: Row) -> RoomDetail:
    tags = await mod_cache.get_room_tags(str(room["id"]))
    attrs = await mod_cache.get_room_attrs(str(room["id"]))
    return RoomDetail(
        id=str(room["id"]),
        room_number=int(room["room_number"]),
        name=str(room["name"]),
        type=str(room["type"]),
        is_private=bool(room["is_private"]),
        is_dm=bool(room["is_dm"]),
        description=str(room["description"]),
        llm_context=str(room["llm_context"]),
        announcement=str(room["announcement"]),
        max_members=int(room["max_members"]),
        slow_mode_sec=int(room["slow_mode_sec"]),
        game_server_url=str(room["game_server_url"])
        if room["game_server_url"] is not None
        else None,
        owner_nickname=await get_owner_nickname(room),
        created_by=str(room["created_by"]),
        created_at=float(room["created_at"]),
        updated_at=float(room["updated_at"]),
        tags=tags,
        attrs=attrs,
    )


async def check_room_access(room: Row) -> None:
    if room["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )


def require_owner(room: Row, current_user: Row) -> None:
    if room["owner_id"] != current_user["id"] and not bool(current_user["is_admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not the room owner"
        )


async def _is_system_room(room_id: str) -> bool:
    """System rooms (room_number < 1000) are never auto-deleted."""
    room = await mod_cache.get_room_row(room_id)
    if room is None:
        return False
    return int(room["room_number"]) < _SYSTEM_ROOM_MAX


async def auto_delete_if_empty(room_id: str, db: DBConn | None = None) -> bool:
    """Soft-delete room if empty. System rooms are exempt."""
    if await _is_system_room(room_id):
        return False
    connected = broadcaster.get_connected_users(room_id)
    if connected:
        return False
    await destroy_game_session(room_id)

    from app.database import get_db_context

    if db is not None:
        await db.execute(
            "UPDATE rooms SET deleted_at = %s WHERE id = %s", (time.time(), room_id)
        )
        await db.commit()
    else:
        async with get_db_context() as conn:
            await conn.execute(
                "UPDATE rooms SET deleted_at = %s WHERE id = %s",
                (time.time(), room_id),
            )
            await conn.commit()
    await mod_cache.invalidate_room(room_id)
    await message_buffer.evict(room_id)
    await broadcaster.broadcast(room_id, "room_deleted", {"room_id": room_id})
    return True


async def transfer_owner_to_oldest(
    room_id: str, current_owner_id: str, db: DBConn
) -> None:
    """Auto-transfer ownership to the oldest connected user when the owner leaves."""
    connected = broadcaster.get_connected_users(room_id)
    candidates = [uid for uid in connected if uid != current_owner_id]
    if not candidates:
        return
    new_owner_id = candidates[0]
    await db.execute(
        "UPDATE rooms SET owner_id = %s WHERE id = %s", (new_owner_id, room_id)
    )
    await db.commit()
    user = await mod_cache.get_user(new_owner_id)
    new_nickname = str(user["nickname"]) if user is not None else ""
    await broadcaster.broadcast(room_id, "owner_changed", {"new_owner": new_nickname})


async def list_rooms(
    tag: str | None,
    room_type: str | None,
    q: str | None,
) -> list[RoomSummary]:
    all_rooms = await mod_cache.get_all_rooms()

    filtered: list[Row] = []
    q_lower = q.lower() if q is not None else None
    for r in all_rooms:
        if room_type is not None and str(r["type"]) != room_type:
            continue
        if q_lower is not None and (
            q_lower not in str(r["name"]).lower()
            and q_lower not in str(r["description"]).lower()
        ):
            continue
        filtered.append(r)

    if not filtered:
        return []

    # Tag filtering requires cache lookup per room
    if tag is not None:
        tagged: list[Row] = []
        for r in filtered:
            tags = await mod_cache.get_room_tags(str(r["id"]))
            if tag in tags:
                tagged.append(r)
        filtered = tagged

    # Tags + owner nicknames (all from cache, no DB)
    tags_by_room: dict[str, list[str]] = {}
    for r in filtered:
        rid = str(r["id"])
        tags_by_room[rid] = await mod_cache.get_room_tags(rid)

    owner_ids = list({str(r["owner_id"]) for r in filtered})
    owner_rows = await mod_cache.get_users_batch(owner_ids)
    nick_by_id = {str(o["id"]): str(o["nickname"]) for o in owner_rows}

    return [
        RoomSummary(
            id=str(r["id"]),
            room_number=int(r["room_number"]),
            name=str(r["name"]),
            type=str(r["type"]),
            is_private=bool(r["is_private"]),
            is_dm=bool(r["is_dm"]),
            description=str(r["description"]),
            announcement=str(r["announcement"]),
            slow_mode_sec=int(r["slow_mode_sec"]),
            max_members=int(r["max_members"]),
            user_count=len(broadcaster.get_connected_users(str(r["id"]))),
            owner_nickname=nick_by_id.get(str(r["owner_id"]), ""),
            created_by=str(r["created_by"]),
            created_at=float(r["created_at"]),
            updated_at=float(r["updated_at"]),
            tags=tags_by_room.get(str(r["id"]), []),
        )
        for r in filtered
    ]


async def _next_room_number(db: DBConn, is_private: bool) -> int:
    """Find the smallest available room_number in the appropriate range."""
    if is_private:
        range_start, range_end = 6000, 9999
    else:
        range_start, range_end = 1000, 5999
    cur = await db.execute(
        "SELECT MIN(n) FROM generate_series(%s::int, %s::int) AS n"
        " WHERE n NOT IN (SELECT room_number FROM rooms WHERE deleted_at IS NULL)",
        (range_start, range_end),
    )
    row = await cur.fetchone()
    result = row["min"] if row is not None else None
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No room numbers available in range",
        )
    return int(result)


async def create_room(body: RoomCreate, current_user: Row, db: DBConn) -> RoomDetail:
    room_id = str(uuid.uuid4())
    now = time.time()

    password_hash: str | None = None
    is_private = body.is_private or bool(body.password)
    if body.password:
        password_hash = hash_password(body.password)

    room_number = await _next_room_number(db, is_private)

    await db.execute(
        """
        INSERT INTO rooms
          (id, room_number, name, type, is_private, is_dm, password_hash, owner_id,
           description, llm_context, announcement, max_members, slow_mode_sec,
           game_server_url, created_by, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, FALSE, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            room_id,
            room_number,
            body.name,
            body.type,
            is_private,
            password_hash,
            current_user["id"],
            body.description,
            body.llm_context,
            body.announcement,
            body.max_members,
            body.slow_mode_sec,
            body.game_server_url,
            current_user["id"],
            now,
            now,
        ),
    )

    await db.execute("INSERT INTO room_seq (room_id, seq) VALUES (%s, 0)", (room_id,))

    await db.execute(
        "INSERT INTO room_members (room_id, user_id, joined_at) VALUES (%s, %s, %s)",
        (room_id, current_user["id"], now),
    )

    for tag in body.tags:
        await db.execute(
            "INSERT INTO room_tags (room_id, tag) VALUES (%s, %s)", (room_id, tag)
        )

    for key, value in body.attrs.items():
        await db.execute(
            "INSERT INTO room_attrs (room_id, key, value) VALUES (%s, %s, %s)",
            (room_id, key, value),
        )

    await db.commit()
    await mod_cache.invalidate_room_list()

    await try_create_game_session(room_id, body, current_user, db)

    room = await mod_cache.get_room_row(room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Room creation failed",
        )
    return await row_to_room_detail(room)


async def resolve_room_id(room_id_or_number: str) -> str:
    """If the input looks like a number, resolve it to a room UUID via cache."""
    if room_id_or_number.isdigit():
        num = int(room_id_or_number)
        all_rooms = await mod_cache.get_all_rooms()
        for r in all_rooms:
            if int(r["room_number"]) == num:
                return str(r["id"])
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    return room_id_or_number


async def get_room(room_id: str) -> RoomDetail:
    room_id = await resolve_room_id(room_id)
    room = await mod_cache.get_room_row(room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    await check_room_access(room)
    return await row_to_room_detail(room)


async def update_room(  # noqa: C901
    room_id: str, body: RoomUpdate, current_user: Row, db: DBConn
) -> RoomDetail:
    room = await mod_cache.get_room_row(room_id)
    if room is None or room["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    require_owner(room, current_user)

    clauses: list[str] = []
    params: list[object] = []
    if body.name is not None:
        clauses.append("name = %s")
        params.append(body.name)
    if body.description is not None:
        clauses.append("description = %s")
        params.append(body.description)
    if body.llm_context is not None:
        clauses.append("llm_context = %s")
        params.append(body.llm_context)
    if body.announcement is not None:
        clauses.append("announcement = %s")
        params.append(body.announcement)
    if body.max_members is not None:
        clauses.append("max_members = %s")
        params.append(body.max_members)
    if body.slow_mode_sec is not None:
        clauses.append("slow_mode_sec = %s")
        params.append(body.slow_mode_sec)
    if body.game_server_url is not None:
        clauses.append("game_server_url = %s")
        params.append(body.game_server_url)

    if clauses:
        clauses.append("updated_at = %s")
        params.append(time.time())
        params.append(room_id)
        set_clause = cast("LiteralString", "UPDATE rooms SET " + ", ".join(clauses))  # noqa: S608
        await db.execute(set_clause + " WHERE id = %s", params)
        await db.commit()
        await mod_cache.invalidate_room(room_id)

    room = await mod_cache.get_room_row(room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    return await row_to_room_detail(room)


async def delete_room(room_id: str, current_user: Row, db: DBConn) -> None:
    room = await mod_cache.get_room_row(room_id)
    if room is None or room["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    require_owner(room, current_user)

    await destroy_game_session(room_id)
    await db.execute(
        "UPDATE rooms SET deleted_at = %s WHERE id = %s", (time.time(), room_id)
    )
    await db.commit()
    await mod_cache.invalidate_room(room_id)
    await broadcaster.broadcast(room_id, "room_deleted", {"room_id": room_id})


async def join_room(room_id: str, body: RoomJoin, current_user: Row) -> None:
    room = await mod_cache.get_room_row(room_id)
    if room is None or room["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )

    globally_banned, room_banned, _ = await mod_cache.check_moderation(
        str(current_user["id"]), room_id
    )
    if globally_banned or room_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Banned")

    if room["max_members"] is not None:
        current_count = len(broadcaster.get_connected_users(room_id))
        if current_count >= int(room["max_members"]):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Room is full"
            )

    if room["password_hash"] is not None and (
        not body.password
        or not verify_password(body.password, str(room["password_hash"]))
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )


async def leave_room(room_id: str, current_user: Row, db: DBConn) -> None:
    room = await mod_cache.get_room_row(room_id)
    if room is None or room["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )

    if room["owner_id"] == current_user["id"]:
        await transfer_owner_to_oldest(room_id, str(current_user["id"]), db)

    await auto_delete_if_empty(room_id, db)


async def transfer_owner(
    room_id: str, body: OwnerTransfer, current_user: Row, db: DBConn
) -> None:
    room = await mod_cache.get_room_row(room_id)
    if room is None or room["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    require_owner(room, current_user)

    target = await mod_cache.get_user(body.user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    await db.execute(
        "UPDATE rooms SET owner_id = %s WHERE id = %s", (body.user_id, room_id)
    )
    await db.commit()
    await mod_cache.invalidate_room(room_id)

    await broadcaster.broadcast(
        room_id, "owner_changed", {"new_owner": target["nickname"]}
    )


async def update_tags(
    room_id: str, tags: list[str], current_user: Row, db: DBConn
) -> dict[str, list[str]]:
    room = await mod_cache.get_room_row(room_id)
    if room is None or room["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    require_owner(room, current_user)

    await db.execute("DELETE FROM room_tags WHERE room_id = %s", (room_id,))
    for tag in tags:
        await db.execute(
            "INSERT INTO room_tags (room_id, tag) VALUES (%s, %s)", (room_id, tag)
        )
    await db.commit()
    await mod_cache.invalidate_room_tags(room_id)

    return {"tags": tags}


async def update_attrs(
    room_id: str, attrs: dict[str, str], current_user: Row, db: DBConn
) -> dict[str, dict[str, str]]:
    room = await mod_cache.get_room_row(room_id)
    if room is None or room["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    require_owner(room, current_user)

    await db.execute("DELETE FROM room_attrs WHERE room_id = %s", (room_id,))
    for key, value in attrs.items():
        await db.execute(
            "INSERT INTO room_attrs (room_id, key, value) VALUES (%s, %s, %s)",
            (room_id, key, value),
        )
    await db.commit()
    await mod_cache.invalidate_room_attrs(room_id)

    return {"attrs": attrs}


async def add_member(
    room_id: str, user_id: str, current_user: Row, db: DBConn
) -> dict[str, str]:
    room = await mod_cache.get_room_row(room_id)
    if room is None or room["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    require_owner(room, current_user)

    target_user = await mod_cache.get_user(user_id)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if await mod_cache.check_room_member(room_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Already a member"
        )

    now = time.time()
    await db.execute(
        "INSERT INTO room_members (room_id, user_id, joined_at) VALUES (%s, %s, %s)",
        (room_id, user_id, now),
    )
    await db.commit()
    await mod_cache.invalidate_room_member(room_id, user_id)
    return {"room_id": room_id, "user_id": user_id}


async def remove_member(
    room_id: str, user_id: str, current_user: Row, db: DBConn
) -> None:
    room = await mod_cache.get_room_row(room_id)
    if room is None or room["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )

    if (
        room["owner_id"] != current_user["id"]
        and not bool(current_user["is_admin"])
        and current_user["id"] != user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    await db.execute(
        "DELETE FROM room_members WHERE room_id = %s AND user_id = %s",
        (room_id, user_id),
    )
    await db.commit()
    await mod_cache.invalidate_room_member(room_id, user_id)


async def stream_setup(token: str, room_id: str) -> tuple[str, str, bool]:
    """
    Authenticate user and validate room access for SSE.

    Returns (user_id, nickname, is_muted).
    """
    from app.security import decode_access_token

    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc

    raw_sub = payload.get("sub")
    user_id = str(raw_sub) if raw_sub is not None else ""
    raw_ver = payload.get("token_version")
    token_version = raw_ver if isinstance(raw_ver, int) else -1

    user = await mod_cache.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if user["token_version"] != token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalidated",
        )

    room = await mod_cache.get_room_row(room_id)
    if room is None or room["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found",
        )
    await check_room_access(room)

    if room["max_members"] is not None:
        n = len(broadcaster.get_connected_users(room_id))
        if n >= int(room["max_members"]):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Room is full",
            )

    globally_banned, room_banned, is_muted = await mod_cache.check_moderation(
        user_id, room_id
    )
    if globally_banned or room_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Banned",
        )
    return user_id, str(user["nickname"]), is_muted


async def get_room_users(room_id: str, _current_user: Row) -> list[UserOut]:
    room = await mod_cache.get_room_row(room_id)
    if room is None or room["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    await check_room_access(room)

    connected_ids = broadcaster.get_connected_users(room_id)
    if not connected_ids:
        return []

    users = await mod_cache.get_users_batch(connected_ids)
    return [
        UserOut(
            id=str(u["id"]),
            email=str(u["email"]),
            nickname=str(u["nickname"]),
            is_admin=bool(u["is_admin"]),
            created_at=float(u["created_at"]),
        )
        for u in users
    ]


async def try_create_game_session(
    room_id: str,
    body: RoomCreate,
    current_user: Row,
    db: DBConn,
) -> None:
    """Create a game session if this is a game room with a scenario."""
    if body.type != "game" or not body.game_server_url:
        return

    scenario_id = body.attrs.get("scenario_id", "")
    if not scenario_id:
        return

    lang = body.attrs.get("lang", "en")
    players = [
        {"id": str(current_user["id"]), "nickname": str(current_user["nickname"])}
    ]

    try:
        session = await relay.create_session(
            body.game_server_url,
            room_id,
            scenario_id,
            lang,
            players,
        )
    except Exception:
        logger.exception("Failed to create game session for room %s", room_id)
        return

    await db.execute(
        "INSERT INTO room_attrs (room_id, key, value)"
        " VALUES (%s, 'game_session_id', %s)"
        " ON CONFLICT (room_id, key) DO UPDATE SET value = %s",
        (room_id, session.session_id, session.session_id),
    )
    await db.commit()

    from app.messages.service import (
        distribute_relay_message,  # lazy import to avoid circular
    )

    for msg in session.messages:
        await distribute_relay_message(room_id, str(current_user["id"]), msg)


async def destroy_game_session(room_id: str) -> None:
    """Destroy the game session associated with a room, if any."""
    room = await mod_cache.get_room_row(room_id)
    if room is None or room["game_server_url"] is None:
        return

    attrs = await mod_cache.get_room_attrs(room_id)
    session_id = attrs.get("game_session_id")
    if session_id is None:
        return

    await relay.destroy_session(str(room["game_server_url"]), session_id)
