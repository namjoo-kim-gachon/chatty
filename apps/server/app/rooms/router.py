from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.database import DBConn, Row, get_db
from app.deps import get_current_user
from app.rooms import service as room_service
from app.rooms.schemas import (
    OwnerTransfer,
    RoomCreate,
    RoomDetail,
    RoomJoin,
    RoomSummary,
    RoomUpdate,
)
from app.sse import broadcaster
from app.users.schemas import UserOut

router = APIRouter(prefix="/rooms", tags=["rooms"])


async def _resolve(room_id: str) -> str:
    """Resolve room_number (digits) to UUID, pass-through otherwise."""
    return await room_service.resolve_room_id(room_id)


@router.get("", response_model=list[RoomSummary])
async def list_rooms(
    tag: str | None = Query(default=None),
    room_type: str | None = Query(default=None, alias="type"),
    q: str | None = Query(default=None),
    _current_user: Row = Depends(get_current_user),
) -> list[RoomSummary]:
    return await room_service.list_rooms(tag, room_type, q)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=RoomDetail)
async def create_room(
    body: RoomCreate,
    current_user: Row = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> RoomDetail:
    return await room_service.create_room(body, current_user, db)


@router.get("/{room_id}", response_model=RoomDetail)
async def get_room(
    room_id: str,
    _current_user: Row = Depends(get_current_user),
) -> RoomDetail:
    return await room_service.get_room(await _resolve(room_id))


@router.patch("/{room_id}", response_model=RoomDetail)
async def update_room(
    room_id: str,
    body: RoomUpdate,
    current_user: Row = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> RoomDetail:
    rid = await _resolve(room_id)
    return await room_service.update_room(rid, body, current_user, db)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room_id: str,
    current_user: Row = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> None:
    await room_service.delete_room(await _resolve(room_id), current_user, db)


@router.post("/{room_id}/join", status_code=status.HTTP_204_NO_CONTENT)
async def join_room(
    room_id: str,
    body: RoomJoin,
    current_user: Row = Depends(get_current_user),
) -> None:
    await room_service.join_room(await _resolve(room_id), body, current_user)


@router.post("/{room_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_room(
    room_id: str,
    current_user: Row = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> None:
    await room_service.leave_room(await _resolve(room_id), current_user, db)


@router.post("/{room_id}/owner", status_code=status.HTTP_204_NO_CONTENT)
async def transfer_owner(
    room_id: str,
    body: OwnerTransfer,
    current_user: Row = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> None:
    await room_service.transfer_owner(await _resolve(room_id), body, current_user, db)


@router.put("/{room_id}/tags")
async def update_tags(
    room_id: str,
    tags: list[str],
    current_user: Row = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> dict[str, list[str]]:
    rid = await _resolve(room_id)
    return await room_service.update_tags(rid, tags, current_user, db)


@router.put("/{room_id}/attrs")
async def update_attrs(
    room_id: str,
    attrs: dict[str, str],
    current_user: Row = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> dict[str, dict[str, str]]:
    rid = await _resolve(room_id)
    return await room_service.update_attrs(rid, attrs, current_user, db)


@router.post("/{room_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    room_id: str,
    body: dict[str, str],
    current_user: Row = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> dict[str, str]:
    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="user_id required"
        )
    rid = await _resolve(room_id)
    return await room_service.add_member(rid, user_id, current_user, db)


@router.delete("/{room_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    room_id: str,
    user_id: str,
    current_user: Row = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> None:
    await room_service.remove_member(await _resolve(room_id), user_id, current_user, db)


@router.get("/{room_id}/stream")
async def stream_room(
    room_id: str,
    authorization: str = Header(...),
) -> StreamingResponse:
    """SSE stream -- DB released before long-lived stream begins."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    token = authorization[7:]

    resolved = await _resolve(room_id)
    user_id, nickname, is_muted = await room_service.stream_setup(token, resolved)
    conn = await broadcaster.connect(resolved, user_id, nickname, is_muted)

    async def generate() -> AsyncIterator[str]:
        async for chunk in broadcaster.stream(conn):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{room_id}/users", response_model=list[UserOut])
async def get_room_users(
    room_id: str,
    current_user: Row = Depends(get_current_user),
) -> list[UserOut]:
    return await room_service.get_room_users(await _resolve(room_id), current_user)
