from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Query, status

from app.database import Row
from app.moderation import cache as mod_cache
from app.security import decode_access_token


def _extract_from_payload(payload: dict[str, object]) -> tuple[str, int]:
    raw_sub = payload.get("sub")
    user_id = str(raw_sub) if raw_sub is not None else ""
    raw_ver = payload.get("token_version")
    token_version = raw_ver if isinstance(raw_ver, int) else -1
    return user_id, token_version


async def authenticate(authorization: str) -> Row:
    """Verify Bearer token and return the authenticated user."""
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc

    user_id, token_version = _extract_from_payload(payload)

    user = await mod_cache.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    if user["token_version"] != token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalidated"
        )

    return user


async def get_current_user(
    authorization: str = Header(...),
) -> Row:
    return await authenticate(authorization)


async def get_current_user_optional(
    authorization: str | None = Header(default=None),
) -> Row | None:
    if authorization is None:
        return None
    try:
        return await authenticate(authorization)
    except HTTPException:
        return None


async def get_current_user_from_query(
    token: str | None = Query(default=None),
) -> Row:
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token required"
        )
    return await authenticate(f"Bearer {token}")


async def require_admin(
    current_user: Row = Depends(get_current_user),
) -> Row:
    if not current_user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin required"
        )
    return current_user
