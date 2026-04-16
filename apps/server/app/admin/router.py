from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.admin.schemas import ReportResolve, SystemMessageCreate
from app.admin.service import (
    delete_user,
    list_reports,
    list_users,
    resolve_report,
    send_system_message,
)
from app.database import DBConn, Row, get_db
from app.deps import require_admin
from app.moderation.schemas import (
    BanCreate,
    BanOut,
    ReportOut,
)
from app.users.schemas import UserOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/rooms/{room_id}/system-message", status_code=status.HTTP_201_CREATED)
async def send_system_message_route(
    room_id: str,
    body: SystemMessageCreate,
    current_user: Row = Depends(require_admin),
    db: DBConn = Depends(get_db),
) -> object:
    return await send_system_message(room_id, body, current_user, db)


@router.get("/users", response_model=list[UserOut])
async def list_users_route(
    _current_user: Row = Depends(require_admin),
    db: DBConn = Depends(get_db),
) -> list[UserOut]:
    return await list_users(db)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_route(
    user_id: str,
    _current_user: Row = Depends(require_admin),
    db: DBConn = Depends(get_db),
) -> None:
    await delete_user(user_id, db)


@router.get("/reports", response_model=list[ReportOut])
async def list_reports_route(
    report_status: str | None = Query(default=None, alias="status"),
    _current_user: Row = Depends(require_admin),
    db: DBConn = Depends(get_db),
) -> list[ReportOut]:
    return await list_reports(report_status, db)


@router.patch("/reports/{report_id}", response_model=ReportOut)
async def resolve_report_route(
    report_id: str,
    body: ReportResolve,
    current_user: Row = Depends(require_admin),
    db: DBConn = Depends(get_db),
) -> ReportOut:
    return await resolve_report(report_id, body, current_user, db)
