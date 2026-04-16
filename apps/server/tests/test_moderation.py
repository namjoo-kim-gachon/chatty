from __future__ import annotations

import time

from httpx import AsyncClient

from tests.conftest import create_room


async def test_room_ban_permanent(
    client: AsyncClient, user_headers: dict, regular_user2: dict, user2_headers: dict
) -> None:
    room = await create_room(client, user_headers, name="BanRoom")

    resp = await client.post(
        f"/rooms/{room['id']}/bans",
        json={"user_id": regular_user2["id"], "reason": "test ban"},
        headers=user_headers,
    )
    assert resp.status_code == 201

    resp = await client.post(
        f"/rooms/{room['id']}/messages",
        json={"text": "I'm banned"},
        headers=user2_headers,
    )
    assert resp.status_code == 403


async def test_room_ban_temporary_expired(
    client: AsyncClient, user_headers: dict, regular_user2: dict, user2_headers: dict
) -> None:
    room = await create_room(client, user_headers, name="TempBanRoom")

    past = time.time() - 1
    resp = await client.post(
        f"/rooms/{room['id']}/bans",
        json={"user_id": regular_user2["id"], "expires_at": past},
        headers=user_headers,
    )
    assert resp.status_code == 201

    resp = await client.post(
        f"/rooms/{room['id']}/messages",
        json={"text": "I'm not banned anymore"},
        headers=user2_headers,
    )
    assert resp.status_code == 201


async def test_unban_user(
    client: AsyncClient, user_headers: dict, regular_user2: dict, user2_headers: dict
) -> None:
    room = await create_room(client, user_headers, name="UnbanRoom")

    await client.post(
        f"/rooms/{room['id']}/bans",
        json={"user_id": regular_user2["id"]},
        headers=user_headers,
    )

    resp = await client.delete(
        f"/rooms/{room['id']}/bans/{regular_user2['id']}",
        headers=user_headers,
    )
    assert resp.status_code == 204

    resp = await client.post(
        f"/rooms/{room['id']}/messages",
        json={"text": "Back!"},
        headers=user2_headers,
    )
    assert resp.status_code == 201


async def test_list_room_bans(
    client: AsyncClient, user_headers: dict, regular_user2: dict
) -> None:
    room = await create_room(client, user_headers, name="ListBanRoom")
    await client.post(
        f"/rooms/{room['id']}/bans",
        json={"user_id": regular_user2["id"], "reason": "listed"},
        headers=user_headers,
    )

    resp = await client.get(f"/rooms/{room['id']}/bans", headers=user_headers)
    assert resp.status_code == 200
    bans = resp.json()
    assert len(bans) == 1
    assert bans[0]["user_id"] == regular_user2["id"]


async def test_room_mute_permanent(
    client: AsyncClient, user_headers: dict, regular_user2: dict, user2_headers: dict
) -> None:
    room = await create_room(client, user_headers, name="MuteRoom")

    resp = await client.post(
        f"/rooms/{room['id']}/mutes",
        json={"user_id": regular_user2["id"], "reason": "muted"},
        headers=user_headers,
    )
    assert resp.status_code == 201

    resp = await client.post(
        f"/rooms/{room['id']}/messages",
        json={"text": "I'm muted"},
        headers=user2_headers,
    )
    assert resp.status_code == 403


async def test_unmute_user(
    client: AsyncClient, user_headers: dict, regular_user2: dict, user2_headers: dict
) -> None:
    room = await create_room(client, user_headers, name="UnmuteRoom")
    await client.post(
        f"/rooms/{room['id']}/mutes",
        json={"user_id": regular_user2["id"]},
        headers=user_headers,
    )

    resp = await client.delete(
        f"/rooms/{room['id']}/mutes/{regular_user2['id']}",
        headers=user_headers,
    )
    assert resp.status_code == 204

    resp = await client.post(
        f"/rooms/{room['id']}/messages",
        json={"text": "unmuted!"},
        headers=user2_headers,
    )
    assert resp.status_code == 201


    assert resp.status_code == 201


async def test_create_report(client: AsyncClient, user2_headers: dict) -> None:
    resp = await client.post(
        "/reports",
        json={
            "target_type": "user",
            "target_id": "some-user-id",
            "reason": "harassment",
            "detail": "details here",
        },
        headers=user2_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["reason"] == "harassment"


async def test_list_my_reports(
    client: AsyncClient, regular_user2: dict, user2_headers: dict
) -> None:
    await client.post(
        "/reports",
        json={"target_type": "message", "target_id": "msg-id", "reason": "spam"},
        headers=user2_headers,
    )

    resp = await client.get("/reports/my", headers=user2_headers)
    assert resp.status_code == 200
    reports = resp.json()
    assert len(reports) >= 1
    assert all(r["reporter_id"] == regular_user2["id"] for r in reports)
