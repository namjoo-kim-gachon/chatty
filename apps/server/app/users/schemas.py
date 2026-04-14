from __future__ import annotations

from pydantic import BaseModel


class UserOut(BaseModel):
    id: str
    email: str
    nickname: str
    is_admin: bool
    created_at: float
