from __future__ import annotations

import time
import uuid
from typing import cast

from fastapi import HTTPException, status
from psycopg.errors import UniqueViolation

from app.database import DBConn
from app.moderation import cache as mod_cache
from app.moderation.schemas import (
    BanCreate,
    BanOut,
    FilterCreate,
    FilterOut,
    MuteCreate,
    MuteOut,
    ReportCreate,
    ReportOut,
)
from app.sse import broadcaster


def _to_float(v: object) -> float:
    return float(cast("float", v))


def _to_float_or_none(v: object) -> float | None:
    if v is None:
        return None
    return float(cast("float", v))


async def require_room_creator_or_admin(
    room_id: str,
    user: dict[str, object],
) -> None:
    room = await mod_cache.get_room_row(room_id)
    if room is None or room["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    if room["created_by"] != user["id"] and not bool(user["is_admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )


# -- Room Bans ----------------------------------------------------------------


async def create_room_ban(
    room_id: str,
    body: BanCreate,
    current_user: dict[str, object],
    db: DBConn,
) -> BanOut:
    ban_id = str(uuid.uuid4())
    now = time.time()
    try:
        await db.execute(
            """
            INSERT INTO room_bans
              (id, room_id, user_id, reason, banned_by, created_at, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                ban_id,
                room_id,
                body.user_id,
                body.reason,
                current_user["id"],
                now,
                body.expires_at,
            ),
        )
        await db.commit()
    except UniqueViolation as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already banned"
        ) from e

    await mod_cache.invalidate_room_ban(room_id, body.user_id)
    await broadcaster.send_to_user(
        room_id,
        body.user_id,
        "banned",
        {"reason": body.reason, "expires_at": body.expires_at},
    )

    user = await mod_cache.get_user(body.user_id)
    nickname = str(user["nickname"]) if user is not None else ""
    return BanOut(
        id=ban_id,
        user_id=body.user_id,
        nickname=nickname,
        reason=body.reason,
        banned_by=str(current_user["id"]),
        created_at=now,
        expires_at=body.expires_at,
    )


async def delete_room_ban(room_id: str, user_id: str, db: DBConn) -> None:
    await db.execute(
        "DELETE FROM room_bans WHERE room_id = %s AND user_id = %s",
        (room_id, user_id),
    )
    await db.commit()
    await mod_cache.invalidate_room_ban(room_id, user_id)


async def list_room_bans(room_id: str, db: DBConn) -> list[BanOut]:
    cur = await db.execute("SELECT * FROM room_bans WHERE room_id = %s", (room_id,))
    rows = await cur.fetchall()
    result: list[BanOut] = []
    for r in rows:
        user = await mod_cache.get_user(str(r["user_id"]))
        nickname = str(user["nickname"]) if user is not None else ""
        result.append(
            BanOut(
                id=str(r["id"]),
                user_id=str(r["user_id"]),
                nickname=nickname,
                reason=str(r["reason"]),
                banned_by=str(r["banned_by"]),
                created_at=_to_float(r["created_at"]),
                expires_at=_to_float_or_none(r["expires_at"]),
            )
        )
    return result


# -- Room Mutes ---------------------------------------------------------------


async def create_room_mute(
    room_id: str,
    body: MuteCreate,
    current_user: dict[str, object],
    db: DBConn,
) -> MuteOut:
    mute_id = str(uuid.uuid4())
    now = time.time()
    try:
        await db.execute(
            """
            INSERT INTO room_mutes
              (id, room_id, user_id, reason, muted_by, created_at, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                mute_id,
                room_id,
                body.user_id,
                body.reason,
                current_user["id"],
                now,
                body.expires_at,
            ),
        )
        await db.commit()
    except UniqueViolation as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already muted"
        ) from e

    await mod_cache.invalidate_room_mute(room_id, body.user_id)
    await broadcaster.send_to_user(
        room_id,
        body.user_id,
        "muted",
        {"reason": body.reason, "expires_at": body.expires_at},
    )

    return MuteOut(
        id=mute_id,
        user_id=body.user_id,
        reason=body.reason,
        muted_by=str(current_user["id"]),
        created_at=now,
        expires_at=body.expires_at,
    )


async def delete_room_mute(room_id: str, user_id: str, db: DBConn) -> None:
    await db.execute(
        "DELETE FROM room_mutes WHERE room_id = %s AND user_id = %s",
        (room_id, user_id),
    )
    await db.commit()
    await mod_cache.invalidate_room_mute(room_id, user_id)
    await broadcaster.send_to_user(room_id, user_id, "unmuted", {})


async def list_room_mutes(room_id: str, db: DBConn) -> list[MuteOut]:
    cur = await db.execute("SELECT * FROM room_mutes WHERE room_id = %s", (room_id,))
    rows = await cur.fetchall()
    return [
        MuteOut(
            id=str(r["id"]),
            user_id=str(r["user_id"]),
            reason=str(r["reason"]),
            muted_by=str(r["muted_by"]),
            created_at=_to_float(r["created_at"]),
            expires_at=_to_float_or_none(r["expires_at"]),
        )
        for r in rows
    ]


# -- Room Filters -------------------------------------------------------------


async def create_room_filter(
    room_id: str,
    body: FilterCreate,
    current_user: dict[str, object],
    db: DBConn,
) -> FilterOut:
    filter_id = str(uuid.uuid4())
    now = time.time()
    await db.execute(
        """
        INSERT INTO room_filters
          (id, room_id, pattern, pattern_type, action, created_by, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            filter_id,
            room_id,
            body.pattern,
            body.pattern_type,
            body.action,
            current_user["id"],
            now,
        ),
    )
    await db.commit()
    await mod_cache.invalidate_room_filters(room_id)

    return FilterOut(
        id=filter_id,
        room_id=room_id,
        pattern=body.pattern,
        pattern_type=body.pattern_type,
        action=body.action,
        created_by=str(current_user["id"]),
        created_at=now,
    )


async def delete_room_filter(room_id: str, filter_id: str, db: DBConn) -> None:
    await db.execute(
        "DELETE FROM room_filters WHERE id = %s AND room_id = %s",
        (filter_id, room_id),
    )
    await db.commit()
    await mod_cache.invalidate_room_filters(room_id)


# -- Reports ------------------------------------------------------------------


async def create_report(
    body: ReportCreate,
    current_user: dict[str, object],
    db: DBConn,
) -> ReportOut:
    report_id = str(uuid.uuid4())
    now = time.time()
    await db.execute(
        """
        INSERT INTO reports
          (id, reporter_id, target_type, target_id, room_id,
           reason, detail, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s)
        """,
        (
            report_id,
            current_user["id"],
            body.target_type,
            body.target_id,
            body.room_id,
            body.reason,
            body.detail,
            now,
        ),
    )
    await db.commit()

    return ReportOut(
        id=report_id,
        reporter_id=str(current_user["id"]),
        target_type=body.target_type,
        target_id=body.target_id,
        room_id=body.room_id,
        reason=body.reason,
        detail=body.detail,
        status="pending",
        resolved_by=None,
        created_at=now,
        resolved_at=None,
    )


async def list_my_reports(
    current_user: dict[str, object],
    db: DBConn,
) -> list[ReportOut]:
    cur = await db.execute(
        "SELECT * FROM reports WHERE reporter_id = %s ORDER BY created_at DESC",
        (current_user["id"],),
    )
    rows = await cur.fetchall()
    return [
        ReportOut(
            id=str(r["id"]),
            reporter_id=str(r["reporter_id"]),
            target_type=str(r["target_type"]),
            target_id=str(r["target_id"]),
            room_id=str(r["room_id"]) if r["room_id"] is not None else None,
            reason=str(r["reason"]),
            detail=str(r["detail"]),
            status=str(r["status"]),
            resolved_by=str(r["resolved_by"]) if r["resolved_by"] is not None else None,
            created_at=_to_float(r["created_at"]),
            resolved_at=_to_float_or_none(r["resolved_at"]),
        )
        for r in rows
    ]
