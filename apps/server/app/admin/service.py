from __future__ import annotations

import time
import uuid

from fastapi import HTTPException, status

from app.admin.schemas import ReportResolve, SystemMessageCreate
from app.auth.service import row_to_user_out
from app.database import DBConn, Row
from app.message_writer import WriteJob
from app.message_writer import enqueue as writer_enqueue
from app.message_writer import next_seq as writer_next_seq
from app.moderation import cache as mod_cache
from app.moderation.schemas import (
    BanCreate,
    BanOut,
    FilterCreate,
    GlobalFilterOut,
    ReportOut,
)
from app.sse import broadcaster
from app.users.schemas import UserOut


async def send_system_message(
    room_id: str, body: SystemMessageCreate, current_user: Row, _db: DBConn
) -> object:
    from app.messages.schemas import MessageOut

    room_meta = await mod_cache.get_room(room_id)
    if room_meta is None or room_meta.is_deleted():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )

    msg_id = str(uuid.uuid4())
    now = time.time()
    seq = await writer_next_seq(room_id)

    msg_out = MessageOut(
        id=msg_id,
        room_id=room_id,
        user_id=str(current_user["id"]),
        nickname="system",
        text=body.text,
        msg_type="system",
        seq=seq,
        created_at=now,
    )
    await broadcaster.broadcast(room_id, "message", msg_out.model_dump())
    writer_enqueue(
        WriteJob(
            msg_id=msg_id,
            room_id=room_id,
            user_id=str(current_user["id"]),
            nickname="system",
            text=body.text,
            msg_type="system",
            seq=seq,
            created_at=now,
        )
    )
    return msg_out


async def list_users(db: DBConn) -> list[UserOut]:
    cur = await db.execute("SELECT * FROM users ORDER BY created_at DESC")
    rows = await cur.fetchall()
    return [row_to_user_out(r) for r in rows]


async def delete_user(user_id: str, db: DBConn) -> None:
    cur = await db.execute("SELECT id FROM users WHERE id = %s", (user_id,))
    user = await cur.fetchone()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    await db.execute("DELETE FROM users WHERE id = %s", (user_id,))
    await db.commit()


async def create_global_ban(body: BanCreate, current_user: Row, db: DBConn) -> BanOut:
    cur = await db.execute("SELECT id FROM users WHERE id = %s", (body.user_id,))
    target = await cur.fetchone()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    ban_id = str(uuid.uuid4())
    now = time.time()
    try:
        await db.execute(
            """
            INSERT INTO global_bans
              (id, user_id, reason, banned_by, created_at, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                ban_id,
                body.user_id,
                body.reason,
                current_user["id"],
                now,
                body.expires_at,
            ),
        )
        await db.commit()
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already globally banned",
            ) from e
        raise

    await mod_cache.invalidate_global_ban(body.user_id)
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


async def delete_global_ban(user_id: str, db: DBConn) -> None:
    await db.execute("DELETE FROM global_bans WHERE user_id = %s", (user_id,))
    await db.commit()
    await mod_cache.invalidate_global_ban(user_id)


async def list_global_bans(db: DBConn) -> list[BanOut]:
    cur = await db.execute("SELECT * FROM global_bans ORDER BY created_at DESC")
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
                created_at=float(r["created_at"]),  # type: ignore[arg-type]
                expires_at=(  # type: ignore[arg-type]
                    float(r["expires_at"]) if r["expires_at"] is not None else None
                ),
            )
        )
    return result


async def list_reports(report_status: str | None, db: DBConn) -> list[ReportOut]:
    if report_status is not None:
        cur = await db.execute(
            "SELECT * FROM reports WHERE status = %s ORDER BY created_at DESC",
            (report_status,),
        )
    else:
        cur = await db.execute("SELECT * FROM reports ORDER BY created_at DESC")
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
            created_at=float(r["created_at"]),  # type: ignore[arg-type]
            resolved_at=float(r["resolved_at"])  # type: ignore[arg-type]
            if r["resolved_at"] is not None
            else None,
        )
        for r in rows
    ]


async def resolve_report(
    report_id: str, body: ReportResolve, current_user: Row, db: DBConn
) -> ReportOut:
    cur = await db.execute("SELECT * FROM reports WHERE id = %s", (report_id,))
    report = await cur.fetchone()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    now = time.time()
    await db.execute(
        "UPDATE reports SET status = %s, resolved_by = %s,"
        " resolved_at = %s WHERE id = %s",
        (body.status, current_user["id"], now, report_id),
    )
    await db.commit()

    cur = await db.execute("SELECT * FROM reports WHERE id = %s", (report_id,))
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report update failed",
        )
    return ReportOut(
        id=str(row["id"]),
        reporter_id=str(row["reporter_id"]),
        target_type=str(row["target_type"]),
        target_id=str(row["target_id"]),
        room_id=str(row["room_id"]) if row["room_id"] is not None else None,
        reason=str(row["reason"]),
        detail=str(row["detail"]),
        status=str(row["status"]),
        resolved_by=str(row["resolved_by"]) if row["resolved_by"] is not None else None,
        created_at=float(row["created_at"]),  # type: ignore[arg-type]
        resolved_at=float(row["resolved_at"])  # type: ignore[arg-type]
        if row["resolved_at"] is not None
        else None,
    )


async def create_global_filter(
    body: FilterCreate, current_user: Row, db: DBConn
) -> GlobalFilterOut:
    filter_id = str(uuid.uuid4())
    now = time.time()
    await db.execute(
        """
        INSERT INTO global_filters
          (id, pattern, pattern_type, action, created_by, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            filter_id,
            body.pattern,
            body.pattern_type,
            body.action,
            current_user["id"],
            now,
        ),
    )
    await db.commit()
    await mod_cache.invalidate_global_filters()

    return GlobalFilterOut(
        id=filter_id,
        pattern=body.pattern,
        pattern_type=body.pattern_type,
        action=body.action,
        created_by=str(current_user["id"]),
        created_at=now,
    )


async def delete_global_filter(filter_id: str, db: DBConn) -> None:
    await db.execute("DELETE FROM global_filters WHERE id = %s", (filter_id,))
    await db.commit()
    await mod_cache.invalidate_global_filters()
