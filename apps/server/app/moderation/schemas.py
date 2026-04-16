from __future__ import annotations

from pydantic import BaseModel, Field


class BanCreate(BaseModel):
    user_id: str
    reason: str = ""
    expires_at: float | None = None


class MuteCreate(BaseModel):
    user_id: str
    reason: str = ""
    expires_at: float | None = None


class BanOut(BaseModel):
    id: str
    user_id: str
    nickname: str
    reason: str
    banned_by: str
    created_at: float
    expires_at: float | None


class MuteOut(BaseModel):
    id: str
    user_id: str
    reason: str
    muted_by: str
    created_at: float
    expires_at: float | None


class ReportCreate(BaseModel):
    target_type: str
    target_id: str
    room_id: str | None = None
    reason: str = Field(min_length=1)
    detail: str = ""


class ReportOut(BaseModel):
    id: str
    reporter_id: str
    target_type: str
    target_id: str
    room_id: str | None
    reason: str
    detail: str
    status: str
    resolved_by: str | None
    created_at: float
    resolved_at: float | None
