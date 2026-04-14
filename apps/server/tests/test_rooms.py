from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import create_room


async def test_create_public_room(client: AsyncClient, user_headers: dict) -> None:
    resp = await client.post(
        "/rooms",
        json={"name": "Public Room", "description": "A test room"},
        headers=user_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Public Room"
    assert data["is_private"] is False
    assert data["is_dm"] is False


async def test_create_private_room(client: AsyncClient, user_headers: dict) -> None:
    resp = await client.post(
        "/rooms",
        json={"name": "Private Room", "is_private": True},
        headers=user_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_private"] is True


async def test_list_rooms_public(
    client: AsyncClient, user_headers: dict, user2_headers: dict
) -> None:
    await create_room(client, user_headers, name="Room1")
    await create_room(client, user_headers, name="Room2")

    resp = await client.get("/rooms", headers=user2_headers)
    assert resp.status_code == 200
    rooms = resp.json()
    names = [r["name"] for r in rooms]
    assert "Room1" in names
    assert "Room2" in names


async def test_list_rooms_private_visible_to_all(
    client: AsyncClient, user_headers: dict, user2_headers: dict
) -> None:
    await create_room(client, user_headers, name="Secret Room", is_private=True)

    resp = await client.get("/rooms", headers=user2_headers)
    rooms = resp.json()
    names = [r["name"] for r in rooms]
    assert "Secret Room" in names


async def test_get_room(client: AsyncClient, user_headers: dict) -> None:
    room = await create_room(
        client, user_headers, name="MyRoom", tags=["gaming", "fun"]
    )
    resp = await client.get(f"/rooms/{room['id']}", headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == room["id"]
    assert set(data["tags"]) == {"gaming", "fun"}


async def test_get_room_with_attrs(client: AsyncClient, user_headers: dict) -> None:
    room = await create_room(
        client, user_headers, name="AttrRoom", attrs={"key1": "val1"}
    )
    resp = await client.get(f"/rooms/{room['id']}", headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["attrs"]["key1"] == "val1"


async def test_get_private_room_visible_to_all(
    client: AsyncClient, user_headers: dict, user2_headers: dict
) -> None:
    room = await create_room(client, user_headers, name="Private", is_private=True)
    resp = await client.get(f"/rooms/{room['id']}", headers=user2_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Private"


async def test_update_room(client: AsyncClient, user_headers: dict) -> None:
    room = await create_room(client, user_headers, name="OldName")
    resp = await client.patch(
        f"/rooms/{room['id']}",
        json={"name": "NewName", "description": "Updated"},
        headers=user_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "NewName"
    assert data["description"] == "Updated"


async def test_update_room_unauthorized(
    client: AsyncClient, user_headers: dict, user2_headers: dict
) -> None:
    room = await create_room(client, user_headers, name="TestRoom")
    resp = await client.patch(
        f"/rooms/{room['id']}",
        json={"name": "HijackedName"},
        headers=user2_headers,
    )
    assert resp.status_code == 403


async def test_delete_room(client: AsyncClient, user_headers: dict) -> None:
    room = await create_room(client, user_headers, name="ToDelete")
    resp = await client.delete(f"/rooms/{room['id']}", headers=user_headers)
    assert resp.status_code == 204

    resp = await client.get(f"/rooms/{room['id']}", headers=user_headers)
    assert resp.status_code == 404


async def test_update_tags(client: AsyncClient, user_headers: dict) -> None:
    room = await create_room(client, user_headers, name="TagRoom", tags=["old"])
    resp = await client.put(
        f"/rooms/{room['id']}/tags",
        json=["new1", "new2"],
        headers=user_headers,
    )
    assert resp.status_code == 200
    assert set(resp.json()["tags"]) == {"new1", "new2"}


async def test_update_attrs(client: AsyncClient, user_headers: dict) -> None:
    room = await create_room(client, user_headers, name="AttrRoom2")
    resp = await client.put(
        f"/rooms/{room['id']}/attrs",
        json={"color": "blue", "mode": "dark"},
        headers=user_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["attrs"]["color"] == "blue"


async def test_add_and_remove_member(
    client: AsyncClient, user_headers: dict, regular_user2: dict
) -> None:
    room = await create_room(client, user_headers, name="MemberRoom", is_private=True)

    resp = await client.post(
        f"/rooms/{room['id']}/members",
        json={"user_id": regular_user2["id"]},
        headers=user_headers,
    )
    assert resp.status_code == 201

    resp = await client.delete(
        f"/rooms/{room['id']}/members/{regular_user2['id']}",
        headers=user_headers,
    )
    assert resp.status_code == 204


async def test_list_rooms_filter_by_tag(
    client: AsyncClient, user_headers: dict
) -> None:
    await create_room(client, user_headers, name="GameRoom", tags=["gaming"])
    await create_room(client, user_headers, name="ChatRoom", tags=["general"])

    resp = await client.get("/rooms?tag=gaming", headers=user_headers)
    rooms = resp.json()
    assert all("gaming" in r["tags"] for r in rooms)
    names = [r["name"] for r in rooms]
    assert "GameRoom" in names
    assert "ChatRoom" not in names


async def test_list_rooms_filter_by_query(
    client: AsyncClient, user_headers: dict
) -> None:
    await create_room(client, user_headers, name="Python Chat")
    await create_room(client, user_headers, name="Java Chat")

    resp = await client.get("/rooms?q=Python", headers=user_headers)
    rooms = resp.json()
    names = [r["name"] for r in rooms]
    assert "Python Chat" in names
    assert "Java Chat" not in names
