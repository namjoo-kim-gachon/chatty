from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any, cast

import psycopg
import pytest
from httpx import ASGITransport, AsyncClient
from psycopg.rows import dict_row

import app.database as db_module
from app import message_writer
from app.database import Row, _make_conn, _run_migration, _seed
from app.main import app
from app.moderation.spam import spam_detector
from app.redis_client import close_redis, init_redis
from app.redis_client import get_redis as _get_redis
from app.security import create_access_token

logger = logging.getLogger(__name__)

_TEST_DB_URL = "postgresql://postgres:cho9942!@localhost/chatty_test"

_TRUNCATE_SQL = """
TRUNCATE TABLE
    messages, room_seq,
    room_filters, global_filters,
    reports, room_mutes, room_bans, global_bans,
    room_members, room_attrs, room_tags, rooms,
    refresh_tokens, users
RESTART IDENTITY CASCADE
"""

# Session-level sync connection for fast schema setup and truncation between tests
_session_sync_conn: psycopg.Connection[Row] | None = None


def _get_session_sync_conn() -> psycopg.Connection[Row]:
    global _session_sync_conn  # noqa: PLW0603
    if _session_sync_conn is None or _session_sync_conn.closed:
        _session_sync_conn = _make_conn(_TEST_DB_URL)
        _run_migration(_session_sync_conn)
    return _session_sync_conn


def _reset_sync_db(conn: psycopg.Connection[Row]) -> None:
    conn.execute(_TRUNCATE_SQL)
    conn.commit()
    _seed(conn)


def _insert_user(
    conn: psycopg.Connection[Row],
    *,
    email: str,
    nickname: str,
    google_id: str | None = None,
    is_admin: bool = False,
) -> dict[str, object]:
    user_id = str(uuid.uuid4())
    now = time.time()
    gid = google_id or str(uuid.uuid4())
    conn.execute(
        "INSERT INTO users"
        " (id, email, nickname, google_id, is_admin, token_version, created_at)"
        " VALUES (%s, %s, %s, %s, %s, 0, %s)",
        (user_id, email, nickname, gid, is_admin, now),
    )
    conn.commit()
    return {
        "id": user_id,
        "email": email,
        "nickname": nickname,
        "is_admin": is_admin,
        "created_at": now,
    }


@pytest.fixture()
async def test_db() -> AsyncGenerator[psycopg.AsyncConnection[Any], None]:
    """Truncate + re-seed via sync conn, then provide a fresh async conn per test."""
    sync_conn = _get_session_sync_conn()
    try:
        sync_conn.rollback()
    except Exception:  # noqa: BLE001
        logger.debug("rollback skipped (no active transaction)")
    _reset_sync_db(sync_conn)

    async_conn = await psycopg.AsyncConnection.connect(
        _TEST_DB_URL, row_factory=dict_row, autocommit=False
    )
    db_module._test_conn = async_conn
    message_writer._test_db_url = _TEST_DB_URL
    spam_detector._history.clear()
    # Ensure Redis is initialized and flush all chatty:* keys between tests
    await init_redis()
    r = _get_redis()
    keys: list[str] = []
    async for key in r.scan_iter("chatty:*"):
        keys.append(key)
    if keys:
        await r.delete(*keys)
    try:
        yield async_conn
    finally:
        message_writer._test_db_url = None
        db_module._test_conn = None
        await async_conn.close()
        await close_redis()


@pytest.fixture(autouse=True)
async def reset_db_fixture(test_db: psycopg.AsyncConnection[Any]) -> None:
    """Ensure test_db is set up before any test runs."""


@pytest.fixture()
async def client(
    test_db: psycopg.AsyncConnection[Any],
) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture()
async def admin_user(test_db: psycopg.AsyncConnection[Any]) -> dict[str, object]:
    return _insert_user(
        _get_session_sync_conn(),
        email="admin@test.com",
        nickname="admin",
        is_admin=True,
    )


@pytest.fixture()
async def regular_user(test_db: psycopg.AsyncConnection[Any]) -> dict[str, object]:
    return _insert_user(
        _get_session_sync_conn(), email="user@test.com", nickname="user1"
    )


@pytest.fixture()
async def regular_user2(test_db: psycopg.AsyncConnection[Any]) -> dict[str, object]:
    return _insert_user(
        _get_session_sync_conn(), email="user2@test.com", nickname="user2"
    )


@pytest.fixture()
def admin_token(admin_user: dict[str, object]) -> str:
    return create_access_token(
        user_id=str(admin_user["id"]),
        nickname=str(admin_user["nickname"]),
        is_admin=bool(admin_user["is_admin"]),
        token_version=0,
    )


@pytest.fixture()
def user_token(regular_user: dict[str, object]) -> str:
    return create_access_token(
        user_id=str(regular_user["id"]),
        nickname=str(regular_user["nickname"]),
        is_admin=bool(regular_user["is_admin"]),
        token_version=0,
    )


@pytest.fixture()
def user2_token(regular_user2: dict[str, object]) -> str:
    return create_access_token(
        user_id=str(regular_user2["id"]),
        nickname=str(regular_user2["nickname"]),
        is_admin=False,
        token_version=0,
    )


@pytest.fixture()
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture()
def user_headers(user_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture()
def user2_headers(user2_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user2_token}"}


async def create_room(
    client: AsyncClient,
    headers: dict[str, str],
    name: str = "Test Room",
    is_private: bool = False,
    **kwargs: object,
) -> dict[str, Any]:
    body: dict[str, object] = {"name": name, "is_private": is_private, **kwargs}
    body.setdefault("slow_mode_sec", 0)
    resp = await client.post(
        "/rooms",
        json=body,
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return cast("dict[str, Any]", resp.json())
