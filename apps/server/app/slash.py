from __future__ import annotations

import time
from dataclasses import dataclass

from fastapi import HTTPException, status

from app.database import get_db_context
from app.moderation import cache as mod_cache
from app.sse import broadcaster


@dataclass
class SlashResult:
    handled: bool
    msg_type: str | None = None
    text: str | None = None
    # If response_only is True, don't persist the message - return directly
    response_only: bool = False
    response_data: object = None


async def _handle_topic(
    args: str,
    room_id: str,
    current_user_id: str,
) -> SlashResult:
    """Handle /topic command."""
    if args:
        room = await mod_cache.get_room_row(room_id)
        if room is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
            )
        if room["owner_id"] != current_user_id:
            user = await mod_cache.get_user(current_user_id)
            if user is None or not bool(user["is_admin"]):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not the room owner",
                )
        async with get_db_context() as db:
            await db.execute(
                "UPDATE rooms SET announcement = %s, updated_at = %s WHERE id = %s",
                (args, time.time(), room_id),
            )
            await db.commit()
        await mod_cache.invalidate_room(room_id)
        await broadcaster.broadcast(room_id, "room_updated", {"announcement": args})
        return SlashResult(
            handled=True,
            response_only=True,
            response_data={"topic": args},
        )
    room = await mod_cache.get_room_row(room_id)
    announcement = room["announcement"] if room else ""
    return SlashResult(
        handled=True,
        response_only=True,
        response_data={"topic": announcement},
    )


async def _handle_who(
    connected_users: list[str],
) -> SlashResult:
    """Handle /who command."""
    if not connected_users:
        return SlashResult(
            handled=True,
            response_only=True,
            response_data={"users": []},
        )
    users = await mod_cache.get_users_batch(connected_users)
    nicknames = [str(u["nickname"]) for u in users]
    return SlashResult(
        handled=True,
        response_only=True,
        response_data={"users": nicknames},
    )


async def _handle_pass(
    args: str,
    room_id: str,
    current_user_id: str,
) -> SlashResult:
    """Handle /pass command."""
    if not args:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="/pass requires a nickname",
        )
    room = await mod_cache.get_room_row(room_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        )
    if room["owner_id"] != current_user_id:
        user = await mod_cache.get_user(current_user_id)
        if user is None or not bool(user["is_admin"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not the room owner",
            )
    target = await mod_cache.get_user_by_nickname(args)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{args}' not found",
        )
    async with get_db_context() as db:
        await db.execute(
            "UPDATE rooms SET owner_id = %s WHERE id = %s", (target["id"], room_id)
        )
        await db.commit()
    await mod_cache.invalidate_room(room_id)
    await broadcaster.broadcast(
        room_id, "owner_changed", {"new_owner": target["nickname"]}
    )
    return SlashResult(
        handled=True,
        response_only=True,
        response_data={"new_owner": target["nickname"]},
    )


async def parse_slash(
    text: str,
    room_id: str,
    connected_users: list[str],
    current_user_id: str = "",
) -> SlashResult:
    if not text.startswith("/"):
        return SlashResult(handled=False)

    parts = text.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if command == "/me":
        action_text = f"* {args}" if args else "* "
        return SlashResult(handled=True, msg_type="action", text=action_text)

    if command == "/topic":
        return await _handle_topic(args, room_id, current_user_id)

    if command == "/who":
        return await _handle_who(connected_users)

    if command == "/pass":
        return await _handle_pass(args, room_id, current_user_id)

    return SlashResult(handled=False)
