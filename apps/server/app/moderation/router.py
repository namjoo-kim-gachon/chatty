from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.database import DBConn, get_db
from app.deps import get_current_user
from app.moderation import service
from app.moderation.schemas import (
    BanCreate,
    BanOut,
    FilterCreate,
    FilterOut,
    MuteCreate,
    MuteOut,
    ReportCreate,
    ReportOut,
)

router = APIRouter(tags=["moderation"])


# -- Room Bans ----------------------------------------------------------------


@router.post(
    "/rooms/{room_id}/bans",
    status_code=status.HTTP_201_CREATED,
    response_model=BanOut,
)
async def create_room_ban(
    room_id: str,
    body: BanCreate,
    current_user: dict[str, object] = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> BanOut:
    await service.require_room_creator_or_admin(room_id, current_user)
    return await service.create_room_ban(room_id, body, current_user, db)


@router.delete(
    "/rooms/{room_id}/bans/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_room_ban(
    room_id: str,
    user_id: str,
    current_user: dict[str, object] = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> None:
    await service.require_room_creator_or_admin(room_id, current_user)
    await service.delete_room_ban(room_id, user_id, db)


@router.get("/rooms/{room_id}/bans", response_model=list[BanOut])
async def list_room_bans(
    room_id: str,
    current_user: dict[str, object] = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> list[BanOut]:
    await service.require_room_creator_or_admin(room_id, current_user)
    return await service.list_room_bans(room_id, db)


# -- Room Mutes ---------------------------------------------------------------


@router.post(
    "/rooms/{room_id}/mutes",
    status_code=status.HTTP_201_CREATED,
    response_model=MuteOut,
)
async def create_room_mute(
    room_id: str,
    body: MuteCreate,
    current_user: dict[str, object] = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> MuteOut:
    await service.require_room_creator_or_admin(room_id, current_user)
    return await service.create_room_mute(room_id, body, current_user, db)


@router.delete(
    "/rooms/{room_id}/mutes/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_room_mute(
    room_id: str,
    user_id: str,
    current_user: dict[str, object] = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> None:
    await service.require_room_creator_or_admin(room_id, current_user)
    await service.delete_room_mute(room_id, user_id, db)


@router.get("/rooms/{room_id}/mutes", response_model=list[MuteOut])
async def list_room_mutes(
    room_id: str,
    current_user: dict[str, object] = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> list[MuteOut]:
    await service.require_room_creator_or_admin(room_id, current_user)
    return await service.list_room_mutes(room_id, db)


# -- Room Filters -------------------------------------------------------------


@router.post(
    "/rooms/{room_id}/filters",
    status_code=status.HTTP_201_CREATED,
    response_model=FilterOut,
)
async def create_room_filter(
    room_id: str,
    body: FilterCreate,
    current_user: dict[str, object] = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> FilterOut:
    await service.require_room_creator_or_admin(room_id, current_user)
    return await service.create_room_filter(room_id, body, current_user, db)


@router.delete(
    "/rooms/{room_id}/filters/{filter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_room_filter(
    room_id: str,
    filter_id: str,
    current_user: dict[str, object] = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> None:
    await service.require_room_creator_or_admin(room_id, current_user)
    await service.delete_room_filter(room_id, filter_id, db)


# -- Reports ------------------------------------------------------------------


@router.post("/reports", status_code=status.HTTP_201_CREATED, response_model=ReportOut)
async def create_report(
    body: ReportCreate,
    current_user: dict[str, object] = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> ReportOut:
    return await service.create_report(body, current_user, db)


@router.get("/reports/my", response_model=list[ReportOut])
async def list_my_reports(
    current_user: dict[str, object] = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> list[ReportOut]:
    return await service.list_my_reports(current_user, db)
