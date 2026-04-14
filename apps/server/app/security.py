from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(
    user_id: str,
    nickname: str,
    is_admin: bool,
    token_version: int,
) -> str:
    expire = datetime.now(UTC) + timedelta(hours=settings.access_token_expire_hours)
    payload = {
        "sub": user_id,
        "nickname": nickname,
        "is_admin": is_admin,
        "token_version": token_version,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, object]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise ValueError("invalid token") from exc
