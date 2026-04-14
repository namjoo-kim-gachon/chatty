"""
Game Relay -- stateless HTTP relay to external game engines.

Chatty knows nothing about game logic. This module simply forwards
player commands to a game engine URL and returns structured responses.

See docs/game-relay-protocol.md for the full protocol specification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import cast

import httpx

logger = logging.getLogger(__name__)

RELAY_TIMEOUT = 5.0


@dataclass
class RelayMessage:
    """A single message returned by the game engine."""

    target: str  # "player" | "others" | "all" | "player:{user_id}"
    type: str  # "game_response" | "system"
    text: str


@dataclass
class SessionCreated:
    """Response from POST /sessions."""

    session_id: str
    messages: list[RelayMessage] = field(default_factory=list)


@dataclass
class CommandResult:
    """Response from POST /sessions/{id}/command."""

    messages: list[RelayMessage] = field(default_factory=list)
    state: dict[str, object] | None = None


class GameRelayError(Exception):
    """Raised when the game engine returns an error."""

    status_code: int
    error: str
    detail: str

    def __init__(self, status_code: int, error: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.error = error
        self.detail = detail


def _parse_messages(raw: list[dict[str, str]]) -> list[RelayMessage]:
    return [
        RelayMessage(
            target=m.get("target", "all"),
            type=m.get("type", "game_response"),
            text=m.get("text", ""),
        )
        for m in raw
    ]


def _check_error(resp: httpx.Response) -> None:
    if resp.status_code >= 400:  # noqa: PLR2004
        try:
            body = resp.json()
            error = str(body.get("error", "unknown"))
            detail = str(body.get("detail", resp.text))
        except Exception:  # noqa: BLE001
            error = "unknown"
            detail = resp.text
        raise GameRelayError(resp.status_code, error, detail)


class GameRelay:
    """Stateless async HTTP relay to external game engines."""

    async def health(self, server_url: str) -> dict[str, object]:
        async with httpx.AsyncClient(timeout=RELAY_TIMEOUT) as client:
            resp = await client.get(f"{server_url}/health")
            _check_error(resp)
            result: dict[str, object] = resp.json()
            return result

    async def create_session(
        self,
        server_url: str,
        room_id: str,
        scenario_id: str,
        lang: str,
        players: list[dict[str, str]],
    ) -> SessionCreated:
        async with httpx.AsyncClient(timeout=RELAY_TIMEOUT) as client:
            resp = await client.post(
                f"{server_url}/sessions",
                json={
                    "room_id": room_id,
                    "scenario_id": scenario_id,
                    "lang": lang,
                    "players": players,
                },
            )
            _check_error(resp)
            data = resp.json()
            return SessionCreated(
                session_id=str(data["session_id"]),
                messages=_parse_messages(data.get("messages", [])),
            )

    async def send_command(
        self,
        server_url: str,
        session_id: str,
        player_id: str,
        nickname: str,
        text: str,
    ) -> CommandResult:
        async with httpx.AsyncClient(timeout=RELAY_TIMEOUT) as client:
            resp = await client.post(
                f"{server_url}/sessions/{session_id}/command",
                json={
                    "player_id": player_id,
                    "nickname": nickname,
                    "text": text,
                },
            )
            _check_error(resp)
            data = resp.json()
            state_raw = data.get("state")
            state: dict[str, object] | None = (
                cast("dict[str, object]", state_raw)
                if isinstance(state_raw, dict)
                else None
            )
            return CommandResult(
                messages=_parse_messages(data.get("messages", [])),
                state=state,
            )

    async def destroy_session(self, server_url: str, session_id: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=RELAY_TIMEOUT) as client:
                resp = await client.delete(f"{server_url}/sessions/{session_id}")
                _check_error(resp)
        except Exception:  # noqa: BLE001
            logger.warning("Failed to destroy game session %s", session_id)


relay = GameRelay()
