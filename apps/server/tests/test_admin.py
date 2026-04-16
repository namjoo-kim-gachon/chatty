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
