from __future__ import annotations

import logging
import time
import uuid

from fastapi import HTTPException, status

from app.database import DBConn, Row, get_db_context
from app.game_relay import GameRelayError, RelayMessage, relay
from app.message_buffer import append as buf_append
from app.message_buffer import get_latest as buf_get_latest
from app.message_buffer import get_since_seq as buf_get_since_seq
from app.message_buffer import warm as buf_warm
from app.message_writer import WriteJob
from app.message_writer import enqueue as writer_enqueue
from app.message_writer import next_seq as writer_next_seq
from app.messages.schemas import MessageCreate, MessageOut
from app.moderation import cache as mod_cache
from app.moderation.enforcer import run_pipeline
from app.rooms.service import check_room_access
from app.slash import parse_slash
from app.sse import broadcaster

logger = logging.getLogger(__name__)


def row_to_message_out(row: Row) -> MessageOut:
    return MessageOut(
        id=str(row["id"]),
        room_id=str(row["room_id"]),
        user_id=str(row["user_id"]),
        nickname=str(row["nickname"]),
        text=str(row["text"]),
        msg_type=str(row["msg_type"]),
        seq=int(row["seq"]),
        created_at=float(row["created_at"]),
    )


async def get_messages(
    room_id: str,
    since_seq: int | None,
    limit: int,
    _current_user: Row,
    db: DBConn,
) -> list[MessageOut]:
    room = await mod_cache.get_room_row(room_id)
    if room is None or room["deleted_at"] is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    await check_room_access(room)

    if since_seq is not None:
        cached = await buf_get_since_seq(room_id, since_seq, limit)
        if cached is not None:
            return cached
        cur = await db.execute(
            "SELECT * FROM messages"
            " WHERE room_id = %s AND seq > %s ORDER BY seq ASC LIMIT %s",
            (room_id, since_seq, limit),
        )
        rows = await cur.fetchall()
        return [row_to_message_out(r) for r in rows]

    cached = await buf_get_latest(room_id, limit)
    if cached is not None:
        return cached
    cur = await db.execute(
        "SELECT * FROM messages WHERE room_id = %s ORDER BY seq DESC LIMIT %s",
        (room_id, limit),
    )
    rows = list(reversed(await cur.fetchall()))
    result = [row_to_message_out(r) for r in rows]
    await buf_warm(room_id, result)
    return result


async def send_message(room_id: str, body: MessageCreate, current_user: Row) -> object:
    room_meta = await mod_cache.get_room(room_id)
    if room_meta is None or room_meta.is_deleted():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    _room_compat: Row = {
        "id": room_id,
        "deleted_at": room_meta.deleted_at,
        "is_private": room_meta.is_private,
    }
    await check_room_access(_room_compat)

    # Check if room is admin-only
    attrs = await mod_cache.get_room_attrs(room_id)
    if attrs.get("admin_only") == "true" and not current_user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can send messages in this room",
        )

    connected_users = broadcaster.get_connected_users(room_id)
    slash_result = await parse_slash(
        body.text, room_id, connected_users, str(current_user["id"])
    )

    if (
        not slash_result.handled
        and room_meta.room_type == "game"
        and room_meta.game_server_url is not None
    ):
        _game_room: Row = {"id": room_id, "game_server_url": room_meta.game_server_url}
        return await handle_game_command(_game_room, current_user, body.text)

    if slash_result.handled and slash_result.response_only:
        return slash_result.response_data

    await run_pipeline(body.text, room_id, str(current_user["id"]))

    # Determine text and msg_type
    text = body.text
    msg_type = "chat"
    if slash_result.handled and slash_result.msg_type is not None:
        msg_type = slash_result.msg_type
        if slash_result.text is not None:
            text = slash_result.text

    # Assign seq from Redis INCR (no DB round-trip, no row lock).
    msg_id = str(uuid.uuid4())
    now = time.time()
    seq = await writer_next_seq(room_id)

    msg_out = MessageOut(
        id=msg_id,
        room_id=room_id,
        user_id=str(current_user["id"]),
        nickname=str(current_user["nickname"]),
        text=text,
        msg_type=msg_type,
        seq=seq,
        created_at=now,
    )

    await buf_append(room_id, msg_out)

    # SSE broadcast before DB write -- connected users receive the message
    # immediately; the DB write happens in the background writer thread.
    await broadcaster.broadcast(room_id, "message", msg_out.model_dump())

    writer_enqueue(
        WriteJob(
            msg_id=msg_id,
            room_id=room_id,
            user_id=str(current_user["id"]),
            nickname=str(current_user["nickname"]),
            text=text,
            msg_type=msg_type,
            seq=seq,
            created_at=now,
        )
    )
    await mod_cache.update_last_msg_at(room_id, str(current_user["id"]), now)

    return msg_out


async def save_message(
    room_id: str,
    user_id: str,
    nickname: str,
    text: str,
    msg_type: str,
) -> MessageOut:
    """Insert a message and return the MessageOut."""
    msg_id = str(uuid.uuid4())
    now = time.time()

    async with get_db_context() as db:
        cur = await db.execute(
            "INSERT INTO room_seq (room_id, seq) VALUES (%s, 1)"
            " ON CONFLICT (room_id) DO UPDATE SET seq = room_seq.seq + 1"
            " RETURNING seq",
            (room_id,),
        )
        seq_row = await cur.fetchone()
        if seq_row is None:
            msg = "Failed to allocate seq"
            raise RuntimeError(msg)
        seq = seq_row["seq"]

        await db.execute(
            """
            INSERT INTO messages
              (id, room_id, user_id, nickname, text, msg_type, seq, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (msg_id, room_id, user_id, nickname, text, msg_type, seq, now),
        )
        await db.commit()

    msg_out = MessageOut(
        id=msg_id,
        room_id=room_id,
        user_id=user_id,
        nickname=nickname,
        text=text,
        msg_type=msg_type,
        seq=int(seq),
        created_at=now,
    )
    await buf_append(room_id, msg_out)
    return msg_out


async def distribute_relay_message(
    room_id: str,
    actor_user_id: str,
    msg: RelayMessage,
) -> None:
    """Save a RelayMessage and distribute via SSE based on target."""
    saved = await save_message(room_id, "system", "system", msg.text, msg.type)
    payload = saved.model_dump()

    if msg.target == "player":
        await broadcaster.send_to_user(room_id, actor_user_id, "message", payload)
    elif msg.target == "others":
        await broadcaster.broadcast_except(room_id, actor_user_id, "message", payload)
    elif msg.target == "all":
        await broadcaster.broadcast(room_id, "message", payload)
    elif msg.target.startswith("player:"):
        target_id = msg.target.split(":", 1)[1]
        await broadcaster.send_to_user(room_id, target_id, "message", payload)


async def handle_game_command(
    room: Row,
    current_user: Row,
    text: str,
) -> object:
    """Forward a player command to the game engine and distribute responses."""
    room_id = str(room["id"])
    user_id = str(current_user["id"])
    nickname = str(current_user["nickname"])
    server_url = str(room["game_server_url"])

    cmd_msg = await save_message(room_id, user_id, nickname, text, "game_command")
    await broadcaster.broadcast(room_id, "message", cmd_msg.model_dump())

    attrs = await mod_cache.get_room_attrs(room_id)
    session_id = attrs.get("game_session_id")
    if session_id is None:
        return cmd_msg

    try:
        result = await relay.send_command(
            server_url, session_id, user_id, nickname, text
        )
    except GameRelayError as exc:
        logger.warning("Game relay error: %s %s", exc.error, exc.detail)
        err_msg = await save_message(
            room_id, user_id, "system", f"[Game error: {exc.detail}]", "system"
        )
        await broadcaster.send_to_user(
            room_id, user_id, "message", err_msg.model_dump()
        )
        return cmd_msg
    except Exception:
        logger.exception("Game relay connection failure")
        err_msg = await save_message(
            room_id, user_id, "system", "[Game server not responding]", "system"
        )
        await broadcaster.send_to_user(
            room_id, user_id, "message", err_msg.model_dump()
        )
        return cmd_msg

    for msg in result.messages:
        await distribute_relay_message(room_id, user_id, msg)

    if result.state is not None:
        await broadcaster.broadcast(room_id, "game_state", result.state)

    return cmd_msg
