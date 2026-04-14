from __future__ import annotations

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4096)


class MessageOut(BaseModel):
    id: str
    room_id: str
    user_id: str
    nickname: str
    text: str
    msg_type: str
    seq: int
    created_at: float
