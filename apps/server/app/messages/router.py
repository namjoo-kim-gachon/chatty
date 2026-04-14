from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.database import DBConn, Row, get_db
from app.deps import get_current_user
from app.messages import service as message_service
from app.messages.schemas import MessageCreate, MessageOut

router = APIRouter(prefix="/rooms", tags=["messages"])


@router.get("/{room_id}/messages", response_model=list[MessageOut])
async def get_messages(
    room_id: str,
    since_seq: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: Row = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> list[MessageOut]:
    return await message_service.get_messages(
        room_id, since_seq, limit, current_user, db
    )


@router.post("/{room_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_message(
    room_id: str,
    body: MessageCreate,
    current_user: Row = Depends(get_current_user),
) -> object:
    return await message_service.send_message(room_id, body, current_user)
