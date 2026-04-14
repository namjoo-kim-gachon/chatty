from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.users.schemas import UserOut

__all__ = [
    "OAuthPollResponse",
    "OAuthStartResponse",
    "RefreshRequest",
    "SetNicknameRequest",
    "TokenPairResponse",
    "UserOut",
]


class OAuthStartResponse(BaseModel):
    url: str
    state: str


class OAuthPollResponse(BaseModel):
    status: Literal["pending", "complete", "error"]
    access_token: str | None = None
    refresh_token: str | None = None
    user: UserOut | None = None
    is_new_user: bool = False
    suggested_nickname: str | None = None
    error: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str


class SetNicknameRequest(BaseModel):
    nickname: str = Field(min_length=2, max_length=32)
