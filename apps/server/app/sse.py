from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import Any

from app.moderation import cache as mod_cache

INACTIVITY_TIMEOUT_SEC = 600  # 10 minutes

_ALLOWED_EVENT_TYPES = frozenset(
    {
        "init",
        "message",
        "user_joined",
        "user_left",
        "kicked",
        "muted",
        "unmuted",
        "banned",
        "room_deleted",
        "room_updated",
        "owner_changed",
        "game_state",
    }
)

_logger = logging.getLogger(__name__)


class SSEConnection:
    user_id: str
    room_id: str

    def __init__(self, user_id: str, room_id: str) -> None:
        self.user_id = user_id
        self.room_id = room_id
        self._queue: asyncio.Queue[dict[str, object] | None] = asyncio.Queue()

    async def put(self, event: dict[str, object] | None) -> None:
        await self._queue.put(event)

    async def get(self) -> dict[str, object] | None:
        return await self._queue.get()


class SSEBroadcaster:
    """Manages SSE connections per room."""

    def __init__(self) -> None:
        # room_id -> {user_id -> SSEConnection}
        self._rooms: dict[str, dict[str, SSEConnection]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._inactivity_timers: dict[str, asyncio.TimerHandle] = {}
        self._on_active: Callable[[str], Coroutine[Any, Any, None]] | None = None
        self._on_inactive: Callable[[str], Coroutine[Any, Any, None]] | None = None
        self._on_room_empty: Callable[[str], Coroutine[Any, Any, None]] | None = None
        # Debounce user_left broadcasts: accumulate per room, flush once per tick
        # Prevents O(N^2) fan-out when N users disconnect simultaneously.
        self._pending_left: dict[str, set[str]] = {}
        self._left_flush_scheduled: set[str] = set()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def set_activity_callbacks(
        self,
        on_active: Callable[[str], Coroutine[Any, Any, None]],
        on_inactive: Callable[[str], Coroutine[Any, Any, None]],
    ) -> None:
        self._on_active = on_active
        self._on_inactive = on_inactive

    def set_room_empty_callback(
        self,
        on_room_empty: Callable[[str], Coroutine[Any, Any, None]],
    ) -> None:
        self._on_room_empty = on_room_empty

    async def connect(
        self, room_id: str, user_id: str, nickname: str, is_muted: bool = False
    ) -> SSEConnection:
        if room_id not in self._rooms:
            self._rooms[room_id] = {}

        # Cancel pending inactivity timer
        pending = self._inactivity_timers.pop(user_id, None)
        if pending is not None:
            pending.cancel()

        # Active callback (fire and forget)
        if self._on_active is not None:
            asyncio.create_task(self._on_active(user_id))

        # Kick existing connection
        existing = self._rooms[room_id].get(user_id)
        if existing is not None:
            asyncio.create_task(existing.put({"event": "kicked", "data": {}}))

        conn = SSEConnection(user_id=user_id, room_id=room_id)
        self._rooms[room_id][user_id] = conn

        # Send initial state to the connecting user before any other events
        await conn.put({"event": "init", "data": {"is_muted": is_muted}})

        # Notify others that a user joined (only if not muted)
        if not is_muted:
            asyncio.create_task(
                self.broadcast_except(
                    room_id,
                    user_id,
                    "user_joined",
                    {"user_id": user_id, "nickname": nickname},
                )
            )

        return conn

    def disconnect(self, room_id: str, user_id: str) -> None:
        room = self._rooms.get(room_id)
        if room is not None:
            room.pop(user_id, None)
            if not room:
                del self._rooms[room_id]

        # Debounced user_left: accumulate all disconnects that happen in the same
        # event-loop tick, then fan-out once.  Avoids O(N^2) when N users leave
        # simultaneously (e.g., mass SSE disconnect after a load test).
        self._pending_left.setdefault(room_id, set()).add(user_id)
        if room_id not in self._left_flush_scheduled:
            self._left_flush_scheduled.add(room_id)
            asyncio.create_task(self._flush_user_left(room_id))

        # Schedule 10-minute inactivity timer
        loop = self._loop
        if loop is not None and loop.is_running() and self._on_inactive is not None:
            handle = loop.call_later(
                INACTIVITY_TIMEOUT_SEC, self._fire_inactive, user_id
            )
            self._inactivity_timers[user_id] = handle

    async def _flush_user_left(self, room_id: str) -> None:
        """
        Emit user_left for all users who left in one event-loop pass.

        Yields once (sleep(0)) so that all synchronous disconnect() calls
        that fired in the same tick have a chance to register before we fan-out.
        This collapses N separate broadcasts into one pass -> O(N*M) instead of
        O(N^2) when N users leave a room with M remaining members.
        """
        await asyncio.sleep(0)
        self._left_flush_scheduled.discard(room_id)
        departed = list(self._pending_left.pop(room_id, set()))
        if not departed:
            return
        room = self._rooms.get(room_id, {})
        if not room:
            # Room is empty -- auto-delete if applicable
            if self._on_room_empty is not None:
                await self._on_room_empty(room_id)
            return
        payload_list: list[dict[str, object]] = []
        for uid in departed:
            # Only broadcast user_left if the departing user was not muted
            _, was_muted = await mod_cache.check_room_moderation(uid, room_id)
            if not was_muted:
                payload_list.append({"event": "user_left", "data": {"user_id": uid}})

        for conn in list(room.values()):
            for payload in payload_list:
                await conn.put(payload)

    def _fire_inactive(self, user_id: str) -> None:
        self._inactivity_timers.pop(user_id, None)
        if self._on_inactive is not None and self._loop is not None:
            self._loop.create_task(self._on_inactive(user_id))

    async def broadcast(self, room_id: str, event_type: str, data: object) -> None:
        room = self._rooms.get(room_id, {})
        payload = {"event": event_type, "data": data}
        for conn in list(room.values()):
            await conn.put(payload)

    def broadcast_threadsafe(self, room_id: str, event_type: str, data: object) -> None:
        """Schedule a broadcast from a synchronous (thread-pool) context."""
        loop = self._loop
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast(room_id, event_type, data),
                loop,
            )

    async def send_to_user(
        self, room_id: str, user_id: str, event_type: str, data: object
    ) -> None:
        """Send an event to a specific user in a room."""
        room = self._rooms.get(room_id, {})
        conn = room.get(user_id)
        if conn is not None:
            await conn.put({"event": event_type, "data": data})

    def send_to_user_threadsafe(
        self, room_id: str, user_id: str, event_type: str, data: object
    ) -> None:
        """Send an event to a specific user from a thread-pool context."""
        loop = self._loop
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.send_to_user(room_id, user_id, event_type, data),
                loop,
            )

    async def broadcast_except(
        self,
        room_id: str,
        exclude_user_id: str,
        event_type: str,
        data: object,
    ) -> None:
        """Broadcast an event to all users in a room except one."""
        room = self._rooms.get(room_id, {})
        payload = {"event": event_type, "data": data}
        for user_id, conn in list(room.items()):
            if user_id != exclude_user_id:
                await conn.put(payload)

    def broadcast_except_threadsafe(
        self,
        room_id: str,
        exclude_user_id: str,
        event_type: str,
        data: object,
    ) -> None:
        """Schedule a broadcast-except from a synchronous context."""
        loop = self._loop
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.broadcast_except(room_id, exclude_user_id, event_type, data),
                loop,
            )

    async def broadcast_join_leave_except(
        self,
        room_id: str,
        exclude_user_id: str,
        event_type: str,
        data: object,
    ) -> None:
        """
        Broadcast a join/leave event to all users in a room except one.

        Skips muted recipients (they shouldn't see join/leave notifications).
        """
        room = self._rooms.get(room_id, {})
        for user_id, conn in list(room.items()):
            if user_id == exclude_user_id:
                continue
            # Check if recipient is muted in this room
            _, is_muted = await mod_cache.check_room_moderation(user_id, room_id)
            if not is_muted:
                await conn.put({"event": event_type, "data": data})

    def get_connected_users(self, room_id: str) -> list[str]:
        """Return user_ids currently connected to a room."""
        return list(self._rooms.get(room_id, {}).keys())

    async def stream(self, conn: SSEConnection) -> AsyncGenerator[str, None]:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(conn.get(), timeout=25)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                if event is None:
                    break
                event_type = str(event.get("event", "message"))
                if event_type not in _ALLOWED_EVENT_TYPES:
                    _logger.warning(
                        "Dropping unknown SSE event type %r for user %s",
                        event_type,
                        conn.user_id,
                    )
                    continue
                data = event.get("data", "")
                if isinstance(data, dict | list):
                    data_str = json.dumps(data)
                else:
                    data_str = str(data)
                yield f"event: {event_type}\ndata: {data_str}\n\n"
        finally:
            self.disconnect(conn.room_id, conn.user_id)


broadcaster = SSEBroadcaster()
