from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

from app.auth.schemas import (
    OAuthPollResponse,
    OAuthStartResponse,
    RefreshRequest,
    SetNicknameRequest,
    TokenPairResponse,
)
from app.config import settings
from app.database import DBConn, Row
from app.moderation import cache as mod_cache
from app.redis_client import get_redis
from app.security import create_access_token
from app.users.schemas import UserOut

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
_OAUTH_STATE_TTL = 600  # 10 minutes


def row_to_user_out(row: dict[str, Any]) -> UserOut:
    return UserOut(
        id=str(row["id"]),
        email=str(row["email"]),
        nickname=str(row["nickname"]),
        is_admin=bool(row["is_admin"]),
        created_at=float(row["created_at"]),
    )


def _google_auth_url(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": f"{settings.base_url}/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"


def _suggest_nickname(name: str) -> str:
    slug = re.sub(r"[^a-z0-9_]", "", name.lower().replace(" ", "_"))
    return slug[:28]


async def start_google_oauth() -> OAuthStartResponse:
    state = str(uuid.uuid4())
    await get_redis().set(f"chatty:oauth:{state}", "pending", ex=_OAUTH_STATE_TTL)
    return OAuthStartResponse(url=_google_auth_url(state), state=state)


async def _exchange_google_code(code: str) -> str | None:
    """Exchange an authorization code for a Google access token."""
    redirect_uri = f"{settings.base_url}/auth/google/callback"
    async with httpx.AsyncClient() as hclient:
        resp = await hclient.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != status.HTTP_200_OK:
        return None
    token_data: dict[str, Any] = resp.json()
    google_access_token = str(token_data.get("access_token", ""))
    return google_access_token or None


async def _get_google_userinfo(
    google_access_token: str,
) -> dict[str, Any] | None:
    """Fetch user profile from Google."""
    async with httpx.AsyncClient() as hclient:
        resp = await hclient.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {google_access_token}"},
        )
    if resp.status_code != status.HTTP_200_OK:
        return None
    return resp.json()  # type: ignore[return-value]


async def _upsert_oauth_user(
    google_id: str, email: str, suggested: str, db: DBConn
) -> tuple[Row | None, bool]:
    """Find or create a user for the given Google account."""
    cur = await db.execute("SELECT * FROM users WHERE google_id = %s", (google_id,))
    existing: Row | None = await cur.fetchone()
    if existing is not None:
        return existing, False

    base = suggested
    nickname = base
    suffix = 1000
    while True:
        cur = await db.execute("SELECT id FROM users WHERE nickname = %s", (nickname,))
        if await cur.fetchone() is None:
            break
        nickname = f"{base}_{suffix}"
        suffix += 1

    user_id = str(uuid.uuid4())
    now = time.time()
    await db.execute(
        "INSERT INTO users"
        " (id, email, nickname, google_id, is_admin, token_version, created_at)"
        " VALUES (%s, %s, %s, %s, FALSE, 0, %s)",
        (user_id, email, nickname, google_id, now),
    )
    await db.commit()
    user = await mod_cache.get_user(user_id)
    return user, True


async def handle_google_callback(code: str, state: str, db: DBConn) -> None:
    r = get_redis()
    raw = await r.get(f"chatty:oauth:{state}")
    if raw != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state",
        )

    async def _store_error(msg: str) -> None:
        await r.set(
            f"chatty:oauth:{state}",
            json.dumps({"error": msg}),
            ex=_OAUTH_STATE_TTL,
        )

    google_access_token = await _exchange_google_code(code)
    if google_access_token is None:
        await _store_error("Google token exchange failed")
        return

    google_info = await _get_google_userinfo(google_access_token)
    if google_info is None:
        await _store_error("Failed to get user info from Google")
        return

    google_id = str(google_info["id"])
    email = str(google_info["email"])
    local_part = email.split("@", 1)[0]
    raw_name = google_info.get("name", local_part)
    name = str(raw_name) if raw_name else local_part
    suggested = _suggest_nickname(name) or _suggest_nickname(local_part) or "user"

    user, is_new_user = await _upsert_oauth_user(google_id, email, suggested, db)
    if user is None:
        await _store_error("User creation failed")
        return

    access_token = create_access_token(
        user_id=str(user["id"]),
        nickname=str(user["nickname"]),
        is_admin=bool(user["is_admin"]),
        token_version=int(user["token_version"]),  # type: ignore[arg-type]
    )

    refresh_token = str(uuid.uuid4())
    now = time.time()
    expires_at = now + settings.refresh_token_expire_days * 86400
    await db.execute(
        "INSERT INTO refresh_tokens (id, user_id, expires_at, created_at)"
        " VALUES (%s, %s, %s, %s)",
        (refresh_token, str(user["id"]), expires_at, now),
    )
    await db.commit()

    result: dict[str, object] = {
        "status": "complete",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": row_to_user_out(user).model_dump(),
        "is_new_user": is_new_user,
        "suggested_nickname": suggested,
    }
    await r.set(f"chatty:oauth:{state}", json.dumps(result), ex=_OAUTH_STATE_TTL)


async def poll_oauth_state(state: str) -> OAuthPollResponse:
    raw = await get_redis().get(f"chatty:oauth:{state}")
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="State not found or expired",
        )

    if raw == "pending":
        return OAuthPollResponse(status="pending")

    data: dict[str, Any] = json.loads(raw)
    if "error" in data:
        return OAuthPollResponse(status="error", error=str(data["error"]))

    user_out = UserOut(**data["user"])
    return OAuthPollResponse(
        status="complete",
        access_token=str(data["access_token"]),
        refresh_token=str(data["refresh_token"]),
        user=user_out,
        is_new_user=bool(data["is_new_user"]),
        suggested_nickname=str(data["suggested_nickname"]),
    )


async def refresh_access_token(body: RefreshRequest, db: DBConn) -> TokenPairResponse:
    now = time.time()
    cur = await db.execute(
        "SELECT rt.id, rt.user_id, rt.expires_at,"
        " u.nickname, u.is_admin, u.token_version"
        " FROM refresh_tokens rt"
        " JOIN users u ON rt.user_id = u.id"
        " WHERE rt.id = %s AND rt.expires_at > %s",
        (body.refresh_token, now),
    )
    rt: Row | None = await cur.fetchone()
    if rt is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    new_rt = str(uuid.uuid4())
    new_expires = now + settings.refresh_token_expire_days * 86400
    await db.execute("DELETE FROM refresh_tokens WHERE id = %s", (body.refresh_token,))
    await db.execute(
        "INSERT INTO refresh_tokens (id, user_id, expires_at, created_at)"
        " VALUES (%s, %s, %s, %s)",
        (new_rt, str(rt["user_id"]), new_expires, now),
    )
    await db.commit()

    access_token = create_access_token(
        user_id=str(rt["user_id"]),
        nickname=str(rt["nickname"]),
        is_admin=bool(rt["is_admin"]),
        token_version=int(rt["token_version"]),  # type: ignore[arg-type]
    )
    return TokenPairResponse(access_token=access_token, refresh_token=new_rt)


async def logout_user(user_id: str, db: DBConn) -> None:
    await db.execute("DELETE FROM refresh_tokens WHERE user_id = %s", (user_id,))
    await db.execute(
        "UPDATE users SET token_version = token_version + 1 WHERE id = %s",
        (user_id,),
    )
    await db.commit()
    await mod_cache.invalidate_user(user_id)


async def set_user_nickname(
    user_id: str, body: SetNicknameRequest, db: DBConn
) -> UserOut:
    cur = await db.execute(
        "SELECT id FROM users WHERE nickname = %s AND id != %s",
        (body.nickname, user_id),
    )
    if await cur.fetchone() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nickname already taken",
        )

    await db.execute(
        "UPDATE users SET nickname = %s WHERE id = %s",
        (body.nickname, user_id),
    )
    await db.commit()
    await mod_cache.invalidate_user(user_id)

    user = await mod_cache.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return row_to_user_out(user)
