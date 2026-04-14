from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import create_room


async def _send(client: AsyncClient, room_id: str, text: str, headers: dict) -> dict:
    resp = await client.post(
        f"/rooms/{room_id}/messages", json={"text": text}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_send_message(client: AsyncClient, user_headers: dict) -> None:
    room = await create_room(client, user_headers, name="MsgRoom")
    msg = await _send(client, room["id"], "Hello!", user_headers)
    assert msg["text"] == "Hello!"
    assert msg["msg_type"] == "chat"
    assert msg["seq"] == 1


async def test_seq_monotonic(
    client: AsyncClient, user_headers: dict, user2_headers: dict
) -> None:
    room = await create_room(client, user_headers, name="SeqRoom")
    headers_cycle = [
        user_headers,
        user2_headers,
        user_headers,
        user2_headers,
        user_headers,
    ]
    seqs = [
        (await _send(client, room["id"], f"unique msg seq{i}", headers_cycle[i]))["seq"]
        for i in range(5)
    ]
    assert seqs == list(range(1, 6))


async def test_get_messages(client: AsyncClient, user_headers: dict) -> None:
    room = await create_room(client, user_headers, name="GetRoom")
    for i in range(3):
        await _send(client, room["id"], f"msg{i}", user_headers)

    resp = await client.get(f"/rooms/{room['id']}/messages", headers=user_headers)
    assert resp.status_code == 200
    msgs = resp.json()
    assert len(msgs) == 3


async def test_get_messages_since_seq(
    client: AsyncClient, user_headers: dict, user2_headers: dict
) -> None:
    room = await create_room(client, user_headers, name="SinceRoom")
    headers_cycle = [
        user_headers,
        user2_headers,
        user_headers,
        user2_headers,
        user_headers,
    ]
    for i in range(5):
        await _send(client, room["id"], f"since msg {i} unique", headers_cycle[i])

    resp = await client.get(
        f"/rooms/{room['id']}/messages?since_seq=2", headers=user_headers
    )
    msgs = resp.json()
    seqs = [m["seq"] for m in msgs]
    assert all(s > 2 for s in seqs)
    assert 3 in seqs and 4 in seqs and 5 in seqs


async def test_slash_me(client: AsyncClient, user_headers: dict) -> None:
    room = await create_room(client, user_headers, name="MeRoom")
    resp = await client.post(
        f"/rooms/{room['id']}/messages",
        json={"text": "/me waves"},
        headers=user_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["msg_type"] == "action"
    assert "waves" in data["text"]


async def test_slash_topic(client: AsyncClient, user_headers: dict) -> None:
    room = await create_room(
        client, user_headers, name="TopicRoom", announcement="Welcome!"
    )
    resp = await client.post(
        f"/rooms/{room['id']}/messages",
        json={"text": "/topic"},
        headers=user_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["topic"] == "Welcome!"


async def test_slash_who(client: AsyncClient, user_headers: dict) -> None:
    room = await create_room(client, user_headers, name="WhoRoom")
    resp = await client.post(
        f"/rooms/{room['id']}/messages",
        json={"text": "/who"},
        headers=user_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "users" in data
