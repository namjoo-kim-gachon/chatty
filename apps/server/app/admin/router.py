from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.admin.schemas import ReportResolve, SystemMessageCreate
from app.admin.service import (
    create_global_ban,
    create_global_filter,
    delete_global_ban,
    delete_global_filter,
    delete_user,
    list_global_bans,
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
    FilterCreate,
    GlobalFilterOut,
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


@router.post("/bans", status_code=status.HTTP_201_CREATED, response_model=BanOut)
async def create_global_ban_route(
    body: BanCreate,
    current_user: Row = Depends(require_admin),
    db: DBConn = Depends(get_db),
) -> BanOut:
    return await create_global_ban(body, current_user, db)


@router.delete("/bans/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_global_ban_route(
    user_id: str,
    _current_user: Row = Depends(require_admin),
    db: DBConn = Depends(get_db),
) -> None:
    await delete_global_ban(user_id, db)


@router.get("/bans", response_model=list[BanOut])
async def list_global_bans_route(
    _current_user: Row = Depends(require_admin),
    db: DBConn = Depends(get_db),
) -> list[BanOut]:
    return await list_global_bans(db)


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


@router.post(
    "/filters",
    status_code=status.HTTP_201_CREATED,
    response_model=GlobalFilterOut,
)
async def create_global_filter_route(
    body: FilterCreate,
    current_user: Row = Depends(require_admin),
    db: DBConn = Depends(get_db),
) -> GlobalFilterOut:
    return await create_global_filter(body, current_user, db)


@router.delete("/filters/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_global_filter_route(
    filter_id: str,
    _current_user: Row = Depends(require_admin),
    db: DBConn = Depends(get_db),
) -> None:
    await delete_global_filter(filter_id, db)
