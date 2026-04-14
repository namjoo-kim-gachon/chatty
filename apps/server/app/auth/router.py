from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import HTMLResponse

from app.auth.schemas import (
    OAuthPollResponse,
    OAuthStartResponse,
    RefreshRequest,
    SetNicknameRequest,
    TokenPairResponse,
)
from app.auth.service import (
    handle_google_callback,
    logout_user,
    poll_oauth_state,
    refresh_access_token,
    row_to_user_out,
    set_user_nickname,
    start_google_oauth,
)
from app.database import DBConn, Row, get_db
from app.deps import get_current_user
from app.users.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger(__name__)

_MESSAGES: dict[str, dict[str, str]] = json.loads(
    (Path(__file__).parent / "callback_messages.json").read_text(encoding="utf-8")
)


def _detect_lang(request: Request) -> str:
    accept = request.headers.get("accept-language", "")
    for part in accept.split(","):
        lang = part.strip().split(";")[0].split("-")[0].lower()
        if lang in _MESSAGES:
            return lang
    return "en"


def _callback_html(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>"
        "<html>"
        "<head><title>Chatty Login</title></head>"
        '<body style="font-family:sans-serif;text-align:center;padding:60px">'
        f"<h2>{title}</h2>"
        f"<p>{body}</p>"
        "</body>"
        "</html>"
    )


@router.get("/google/start", response_model=OAuthStartResponse)
async def google_start() -> OAuthStartResponse:
    return await start_google_oauth()


@router.get("/google/callback", response_class=HTMLResponse)
async def google_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: DBConn = Depends(get_db),
) -> HTMLResponse:
    lang = _detect_lang(request)
    msgs = _MESSAGES[lang]
    try:
        await handle_google_callback(code, state, db)
        return HTMLResponse(
            content=_callback_html(msgs["success_title"], msgs["success_body"])
        )
    except Exception:
        logger.exception("OAuth callback failed")
        return HTMLResponse(
            content=_callback_html(msgs["error_title"], msgs["error_body"]),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@router.get("/poll/{state}", response_model=OAuthPollResponse)
async def poll(state: str) -> OAuthPollResponse:
    return await poll_oauth_state(state)


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(
    body: RefreshRequest, db: DBConn = Depends(get_db)
) -> TokenPairResponse:
    return await refresh_access_token(body, db)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: Row = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> None:
    await logout_user(str(current_user["id"]), db)


@router.get("/me", response_model=UserOut)
async def me(current_user: Row = Depends(get_current_user)) -> UserOut:
    return row_to_user_out(current_user)


@router.patch("/me/nickname", response_model=UserOut)
async def update_nickname(
    body: SetNicknameRequest,
    current_user: Row = Depends(get_current_user),
    db: DBConn = Depends(get_db),
) -> UserOut:
    return await set_user_nickname(str(current_user["id"]), body, db)
