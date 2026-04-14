from __future__ import annotations

import time
import uuid

import psycopg
from httpx import AsyncClient


async def test_me(client: AsyncClient, regular_user: dict, user_headers: dict) -> None:
    resp = await client.get("/auth/me", headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == regular_user["id"]
    assert data["nickname"] == regular_user["nickname"]


async def test_me_unauthorized(client: AsyncClient) -> None:
    resp = await client.get(
        "/auth/me", headers={"Authorization": "Bearer invalidtoken"}
    )
    assert resp.status_code == 401


async def test_google_start_returns_url(client: AsyncClient) -> None:
    resp = await client.get("/auth/google/start")
    assert resp.status_code == 200
    data = resp.json()
    assert "url" in data
    assert "state" in data
    assert "accounts.google.com" in data["url"]


async def test_poll_pending(client: AsyncClient) -> None:
    start = await client.get("/auth/google/start")
    state = start.json()["state"]

    resp = await client.get(f"/auth/poll/{state}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


async def test_poll_unknown_state(client: AsyncClient) -> None:
    resp = await client.get(f"/auth/poll/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_refresh_invalid_token(client: AsyncClient) -> None:
    resp = await client.post("/auth/refresh", json={"refresh_token": str(uuid.uuid4())})
    assert resp.status_code == 401


async def test_refresh_success(
    client: AsyncClient,
    regular_user: dict,
    test_db: psycopg.AsyncConnection,
) -> None:
    rt_id = str(uuid.uuid4())
    now = time.time()
    expires_at = now + 86400 * 30

    await test_db.execute(
        "INSERT INTO refresh_tokens (id, user_id, expires_at, created_at)"
        " VALUES (%s, %s, %s, %s)",
        (rt_id, regular_user["id"], expires_at, now),
    )
    await test_db.commit()

    resp = await client.post("/auth/refresh", json={"refresh_token": rt_id})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] != rt_id  # rotated


async def test_logout_invalidates_token(
    client: AsyncClient, user_headers: dict
) -> None:
    resp = await client.post("/auth/logout", headers=user_headers)
    assert resp.status_code == 204

    resp = await client.get("/auth/me", headers=user_headers)
    assert resp.status_code == 401


async def test_update_nickname_success(
    client: AsyncClient, regular_user: dict, user_headers: dict
) -> None:
    resp = await client.patch(
        "/auth/me/nickname",
        json={"nickname": "newnick"},
        headers=user_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["nickname"] == "newnick"


async def test_update_nickname_conflict(
    client: AsyncClient, admin_user: dict, regular_user: dict, user_headers: dict
) -> None:
    resp = await client.patch(
        "/auth/me/nickname",
        json={"nickname": admin_user["nickname"]},
        headers=user_headers,
    )
    assert resp.status_code == 409
