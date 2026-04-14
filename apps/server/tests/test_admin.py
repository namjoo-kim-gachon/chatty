from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import create_room


async def test_send_system_message(client: AsyncClient, admin_headers: dict) -> None:
    room = await create_room(client, admin_headers, name="SysRoom")
    resp = await client.post(
        f"/admin/rooms/{room['id']}/system-message",
        json={"text": "System announcement"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["msg_type"] == "system"
    assert data["text"] == "System announcement"


async def test_send_system_message_requires_admin(
    client: AsyncClient, user_headers: dict
) -> None:
    room = await create_room(client, user_headers, name="NoSysRoom")
    resp = await client.post(
        f"/admin/rooms/{room['id']}/system-message",
        json={"text": "Unauthorized"},
        headers=user_headers,
    )
    assert resp.status_code == 403


async def test_list_users(
    client: AsyncClient, admin_headers: dict, regular_user: dict, regular_user2: dict
) -> None:
    resp = await client.get("/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    users = resp.json()
    ids = [u["id"] for u in users]
    assert regular_user["id"] in ids
    assert regular_user2["id"] in ids


async def test_list_users_requires_admin(
    client: AsyncClient, user_headers: dict
) -> None:
    resp = await client.get("/admin/users", headers=user_headers)
    assert resp.status_code == 403


async def test_delete_user(
    client: AsyncClient, admin_headers: dict, regular_user2: dict
) -> None:
    resp = await client.delete(
        f"/admin/users/{regular_user2['id']}", headers=admin_headers
    )
    assert resp.status_code == 204

    resp = await client.get("/admin/users", headers=admin_headers)
    ids = [u["id"] for u in resp.json()]
    assert regular_user2["id"] not in ids


async def test_global_ban(
    client: AsyncClient,
    admin_headers: dict,
    regular_user2: dict,
    user2_headers: dict,
    user_headers: dict,
) -> None:
    room = await create_room(client, user_headers, name="GBanRoom")

    resp = await client.post(
        "/admin/bans",
        json={"user_id": regular_user2["id"], "reason": "global test ban"},
        headers=admin_headers,
    )
    assert resp.status_code == 201

    resp = await client.post(
        f"/rooms/{room['id']}/messages",
        json={"text": "globally banned"},
        headers=user2_headers,
    )
    assert resp.status_code == 403


async def test_global_unban(
    client: AsyncClient,
    admin_headers: dict,
    regular_user2: dict,
    user2_headers: dict,
    user_headers: dict,
) -> None:
    room = await create_room(client, user_headers, name="GUnbanRoom")
    await client.post(
        "/admin/bans",
        json={"user_id": regular_user2["id"]},
        headers=admin_headers,
    )

    resp = await client.delete(
        f"/admin/bans/{regular_user2['id']}", headers=admin_headers
    )
    assert resp.status_code == 204

    resp = await client.post(
        f"/rooms/{room['id']}/messages",
        json={"text": "free now"},
        headers=user2_headers,
    )
    assert resp.status_code == 201


async def test_list_global_bans(
    client: AsyncClient, admin_headers: dict, regular_user2: dict
) -> None:
    await client.post(
        "/admin/bans",
        json={"user_id": regular_user2["id"]},
        headers=admin_headers,
    )
    resp = await client.get("/admin/bans", headers=admin_headers)
    assert resp.status_code == 200
    bans = resp.json()
    assert any(b["user_id"] == regular_user2["id"] for b in bans)


async def test_list_reports(
    client: AsyncClient, admin_headers: dict, user_headers: dict
) -> None:
    await client.post(
        "/reports",
        json={"target_type": "user", "target_id": "some-id", "reason": "test"},
        headers=user_headers,
    )

    resp = await client.get("/admin/reports", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_list_reports_filter_by_status(
    client: AsyncClient, admin_headers: dict, user_headers: dict
) -> None:
    await client.post(
        "/reports",
        json={"target_type": "user", "target_id": "x", "reason": "test"},
        headers=user_headers,
    )

    resp = await client.get("/admin/reports?status=pending", headers=admin_headers)
    assert resp.status_code == 200
    reports = resp.json()
    assert all(r["status"] == "pending" for r in reports)


async def test_resolve_report(
    client: AsyncClient, admin_headers: dict, user_headers: dict
) -> None:
    report_resp = await client.post(
        "/reports",
        json={"target_type": "user", "target_id": "x", "reason": "test"},
        headers=user_headers,
    )
    report_id = report_resp.json()["id"]

    resp = await client.patch(
        f"/admin/reports/{report_id}",
        json={"status": "resolved"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    assert data["resolved_by"] is not None
    assert data["resolved_at"] is not None


async def test_create_global_filter(
    client: AsyncClient, admin_headers: dict, user_headers: dict
) -> None:
    room = await create_room(client, user_headers, name="GFRoom")

    resp = await client.post(
        "/admin/filters",
        json={"pattern": "globalblock", "pattern_type": "keyword"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["pattern"] == "globalblock"

    resp = await client.post(
        f"/rooms/{room['id']}/messages",
        json={"text": "this has globalblock in it"},
        headers=user_headers,
    )
    assert resp.status_code == 403


async def test_delete_global_filter(
    client: AsyncClient, admin_headers: dict, user_headers: dict
) -> None:
    room = await create_room(client, user_headers, name="GFDelRoom")

    filter_resp = await client.post(
        "/admin/filters",
        json={"pattern": "removeme"},
        headers=admin_headers,
    )
    filter_id = filter_resp.json()["id"]

    await client.delete(f"/admin/filters/{filter_id}", headers=admin_headers)

    resp = await client.post(
        f"/rooms/{room['id']}/messages",
        json={"text": "word removeme is ok now"},
        headers=user_headers,
    )
    assert resp.status_code == 201
