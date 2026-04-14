from __future__ import annotations

from pydantic import BaseModel, Field


class SystemMessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4096)


class ReportResolve(BaseModel):
    status: str
