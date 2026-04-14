# Game Relay Protocol

HTTP relay protocol for communicating with external game engines in Chatty's game rooms (`room.type == "game"`).

## Goal

- Chatty **knows nothing about game logic**. It merely relays via URL and distributes responses.
- Any game engine can connect to Chatty by implementing the 4 endpoints below.
- Supports all genres -- escape rooms, MUD, quizzes, board games, AI chatrooms -- with the same contract.

## Architecture

```
  Player --REST--> Chatty Server --HTTP--> Game Engine
                       |                       |
                       |<---- JSON response ----+
                       |
                  SSE distribution:
                  |-- Actor:     send_to_user
                  |-- Observers: broadcast_except
                  +-- Everyone:  broadcast
```

---

## Game Engine Contract

HTTP API that the game engine must implement.  
All endpoints are relative to the `game_server_url` configured on the room (must be an absolute URL, e.g. `http://game-engine:3000`).

### `GET /health`

Health check and scenario list retrieval.

**Response 200:**

```json
{
  "engine": "escape-forge",
  "version": "1.0.0",
  "scenarios": [
    {
      "id": "cabin_escape",
      "name": "Cabin Escape",
      "lang": ["en", "ko"],
      "max_players": 4,
      "description": "Escape from a mysterious cabin"
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `engine` | string | Y | Engine identifier |
| `version` | string | Y | Engine version |
| `scenarios` | array | Y | List of available scenarios |
| `scenarios[].id` | string | Y | Unique scenario ID |
| `scenarios[].name` | string | Y | Display name |
| `scenarios[].lang` | string[] | Y | Supported language list |
| `scenarios[].max_players` | int | N | Maximum player count (null means unlimited) |
| `scenarios[].description` | string | N | Scenario description |

---

### `POST /sessions`

Create a game session. Called by Chatty when starting a game room.

**Request:**

```json
{
  "room_id": "chatty-room-uuid",
  "scenario_id": "cabin_escape",
  "lang": "ko",
  "players": [
    { "id": "user-uuid-1", "nickname": "Alice" }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `room_id` | string | Y | Chatty room ID (external reference key) |
| `scenario_id` | string | Y | Scenario ID |
| `lang` | string | Y | Language code |
| `players` | array | Y | Initial player list |
| `players[].id` | string | Y | Chatty user ID |
| `players[].nickname` | string | Y | Nickname |

**Response 201:**

```json
{
  "session_id": "engine-session-uuid",
  "messages": [
    { "target": "all", "type": "system",        "text": "=== Cabin Escape ===" },
    { "target": "all", "type": "game_response", "text": "You are trapped in a dark cabin..." }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | Y | Session ID issued by the engine |
| `messages` | RelayMessage[] | Y | Initial messages (title, intro, first look result, etc.) |

---

### `POST /sessions/{session_id}/command`

Process a player command. **Core endpoint.**

**Request:**

```json
{
  "player_id": "user-uuid-1",
  "nickname": "Alice",
  "text": "/x statue"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `player_id` | string | Y | Chatty user ID |
| `nickname` | string | Y | Nickname |
| `text` | string | Y | Original input |

**Response 200:**

```json
{
  "messages": [
    {
      "target": "player",
      "type": "game_response",
      "text": "An old statue. It looks like it needs a coin."
    },
    {
      "target": "others",
      "type": "game_response",
      "text": "Alice examines the statue."
    }
  ],
  "state": {
    "stage": 1,
    "inventory": ["coin"],
    "game_over": false,
    "won": false
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `messages` | RelayMessage[] | Y | Response message list |
| `state` | object | N | Game state summary (for client UI hints) |

---

### `DELETE /sessions/{session_id}`

End session. Called on room deletion or game over.

**Response 204 (No Content)**

---

## RelayMessage Format

Common structure for messages returned by all endpoints:

```json
{
  "target": "player",
  "type": "game_response",
  "text": "..."
}
```

### `target` Field

| Value | Meaning | Chatty Action |
|-------|---------|---------------|
| `"player"` | Only to the player who sent the command | `send_to_user` |
| `"others"` | Entire room **excluding** the actor | `broadcast_except` |
| `"all"` | Entire room | `broadcast` |
| `"player:{user_id}"` | Specific player designated | `send_to_user(user_id)` |

### `type` Field

| Value | Meaning | Client Rendering |
|-------|---------|------------------|
| `"game_response"` | Game response | Green, `>>>` prefix |
| `"system"` | System notification | Yellow, `***` prefix |

---

## Error Responses

Common format when the game engine returns an error:

```json
{
  "error": "error_code",
  "detail": "Human-readable description"
}
```

| HTTP Code | error Code | Meaning | Chatty Response |
|-----------|-----------|---------|-----------------|
| 404 | `session_not_found` | Session missing/expired | Attempt to create new session |
| 400 | `invalid_command` | Invalid input | Forward error to actor as game_response |
| 409 | `game_over` | Game already ended | System message notification |
| 503 | `unavailable` | Engine overloaded | "Please try again later" system message |

**Timeout**: If Chatty receives no response after 5 seconds, it sends a "Game server not responding" system message to the actor.

---

## Session Lifecycle

```
  Room creation + scenario selection
         |
         v
  POST /sessions -------> session_id issued
         |                   |
         |              attrs["game_session_id"] stored
         |                   |
         v                   v
  Player joins           Initial messages broadcast
         |
         v
  POST /sessions/{id}/command <---- repeats
         |
         |-- state.game_over == true -> game over system message
         |
         v
  Room deletion / empty room auto-delete
         |
         v
  DELETE /sessions/{id}
```

### Session Tracking via room_attrs

| Key | Value | Description |
|-----|-------|-------------|
| `game_session_id` | Session ID issued by engine | Session identification |
| `scenario_id` | Scenario ID | Which game |
| `lang` | Language code | Game language |

---

## Coexistence with Chatty Slash Commands

Chatty's built-in slash commands (`/who`, `/topic`, `/pass`) must still work in game rooms.

**Priority:**

1. `parse_slash()` -- Is it a Chatty slash command?
   - `handled=True` -> Chatty handles it directly. Not sent to game engine.
   - `handled=False` -> Next step.
2. `room.type == "game"` -> Relay to game engine (everything, whether slash or not).
3. Normal chat -> Standard message save.

---

## SSE Events

### Existing Events (no changes)

`message`, `message_updated`, `message_deleted`, `user_joined`, `user_left`,
`system`, `room_updated`, `kicked`, `banned`, `muted`, `unmuted`,
`owner_changed`, `room_deleted`

### New Events

| Event | Data | Description |
|-------|------|-------------|
| `game_state` | `{ stage?, inventory?, game_over?, won?, ... }` | Game state summary. Broadcast to entire room when engine returns `state`. |

---

## Sequence Diagrams

### Game Room Creation

```
  Owner (TUI)             Chatty Server              Game Engine
  -----------      ---------------------      ------------------
  POST /rooms
  { type: "game",
    game_server_url: "http://...",
    attrs: {
      scenario_id: "cabin",
      lang: "ko"
    } }
        ---------->  create_room()
                       |
                       |  POST /sessions
                       |  { room_id, scenario_id, lang, players }
                       |  ---------------------------------------->
                       |
                       |  < { session_id: "s1", messages: [...] }
                       |
                       |  attrs["game_session_id"] = "s1"
                       |  broadcast: initial messages
        <-- SSE -------|
```

### Command Execution

```
  Alice (TUI)             Chatty Server              Game Engine
  -----------      ---------------------      ------------------
  POST /messages
  { text: "/x statue" }
        ---------->  send_message()
                       |
                       |  1) save game_command & broadcast
        <-- SSE -------|---> Bob
                       |
                       |  2) POST /sessions/s1/command
                       |     { player_id, nickname, text }
                       |  ------------------------------>
                       |
                       |  < { messages: [
                       |      {target:"player", text:"An old statue..."},
                       |      {target:"others", text:"Alice examines the statue."}
                       |    ], state: {...} }
                       |
                       |  3) send_to_user(alice): game_response
        <-- SSE -------|
                       |  4) broadcast_except(alice): game_response
                       |-----------> Bob
                       |
                       |  5) broadcast: game_state
        <-- SSE -------|---> Bob
```

---

## Various Engine Application Examples

| Game Engine | scenario_id | Command Response Pattern | State Example |
|-------------|-------------|--------------------------|---------------|
| Escape room (escape-forge) | `cabin_escape` | actor/others split | `{ stage, inventory }` |
| MUD | `dark_forest` | room description, combat log | `{ hp, location, score }` |
| Quiz | `trivia_kr` | question is `all`, answer is `player` | `{ score, remaining }` |
| Mafia | `mafia_6p` | night is `player:{id}`, day is `all` | `{ phase, alive }` |
| AI Chat | `gpt_chat` | all responses `all` | N/A |
