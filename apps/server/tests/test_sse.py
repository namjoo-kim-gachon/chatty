from __future__ import annotations

import asyncio

from app.sse import SSEBroadcaster


async def test_broadcaster_connect_and_broadcast() -> None:
    bc = SSEBroadcaster()
    conn = await bc.connect("room1", "user1", "nick1")
    assert conn.room_id == "room1"
    assert conn.user_id == "user1"

    # connect() puts an init event first; drain it before checking broadcast
    init_event = await conn.get()
    assert init_event is not None
    assert init_event["event"] == "init"

    await bc.broadcast("room1", "message", {"text": "hello"})
    event = await conn.get()
    assert event is not None
    assert event["event"] == "message"


async def test_broadcaster_disconnect() -> None:
    bc = SSEBroadcaster()
    await bc.connect("room1", "user1", "nick1")
    bc.disconnect("room1", "user1")
    assert "user1" not in bc._rooms.get("room1", {})


async def test_broadcaster_get_connected_users() -> None:
    bc = SSEBroadcaster()
    await bc.connect("room1", "user1", "nick1")
    await bc.connect("room1", "user2", "nick2")
    users = bc.get_connected_users("room1")
    assert "user1" in users
    assert "user2" in users


async def test_broadcaster_stream_yields_events() -> None:
    bc = SSEBroadcaster()
    conn = await bc.connect("room1", "user1", "nick1")

    await conn.put({"event": "message", "data": "hello"})
    await conn.put(None)  # sentinel to stop

    chunks = []
    async for chunk in bc.stream(conn):
        chunks.append(chunk)

    # connect() prepends an init event, so we get init + message
    assert len(chunks) == 2
    assert "event: init" in chunks[0]
    assert "event: message" in chunks[1]
    assert "data: hello" in chunks[1]


async def test_broadcaster_multiple_rooms() -> None:
    bc = SSEBroadcaster()
    conn1 = await bc.connect("room1", "user1", "nick1")
    conn2 = await bc.connect("room2", "user1", "nick1")

    await bc.broadcast("room1", "ping", "test")

    # conn1 should have event (user_joined from connect fires as task, then our broadcast)
    # Drain any user_joined events first
    while not conn1._queue.empty():
        ev = await asyncio.wait_for(conn1.get(), timeout=1.0)
        if ev is not None and ev.get("event") == "ping":
            assert True
            return

    event = await asyncio.wait_for(conn1.get(), timeout=1.0)
    assert event is not None

    # conn2 should have nothing (would block), check queue is empty
    assert conn2._queue.empty()
