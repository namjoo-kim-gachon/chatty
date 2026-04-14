from __future__ import annotations

from pydantic import BaseModel, Field


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    type: str = "chat"
    is_private: bool = False
    password: str | None = None
    description: str = ""
    llm_context: str = ""
    announcement: str = ""
    max_members: int = Field(default=500, ge=2, le=500)
    slow_mode_sec: int = Field(default=1, ge=0, le=99)
    game_server_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    attrs: dict[str, str] = Field(default_factory=dict)


class RoomUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    llm_context: str | None = None
    announcement: str | None = None
    max_members: int | None = Field(default=None, ge=2, le=500)
    slow_mode_sec: int | None = Field(default=None, ge=0, le=99)
    game_server_url: str | None = None


class RoomJoin(BaseModel):
    password: str | None = None


class OwnerTransfer(BaseModel):
    user_id: str


class RoomSummary(BaseModel):
    id: str
    room_number: int
    name: str
    type: str
    is_private: bool
    is_dm: bool
    description: str
    announcement: str
    slow_mode_sec: int
    max_members: int
    user_count: int = 0
    owner_nickname: str
    created_by: str
    created_at: float
    updated_at: float
    tags: list[str] = Field(default_factory=list)


class RoomDetail(RoomSummary):
    llm_context: str
    max_members: int
    game_server_url: str | None
    attrs: dict[str, str] = Field(default_factory=dict)
