# Chatty Server -- Implementation Plan

## Overview

**Location**: `/Users/namjookim/projects/chatty/apps/server/`  
**Tech Stack**: Python 3.12 + FastAPI + PostgreSQL  
**Package Management**: `uv` only (no pip/poetry)  
**Role**: Chat gateway server -- authentication, room management, message broadcast

---

## User Flow

```
App launch -> Login
  -> If last room exists, auto-join (if room deleted, go to waiting room)
  -> If no last room, auto-join waiting room (#waiting)

During chat:
  /rooms     -> Room list screen (search, join)
  /join <rm> -> Direct join (prompts for password if private)
  /leave     -> Return to waiting room (from waiting room: exit program)
  /create    -> Room creation form
  /who       -> Connected users list screen
  /topic     -> View announcement (room owner: /topic <content> to set)
  /pass <nick> -> Transfer ownership (owner only)
  /me <action> -> Action message

Leaving a room:
  -> If 0 members remain, room is auto-deleted (waiting room is exempt)
  -> If the owner leaves, ownership is auto-transferred to the longest-connected user
```

---

## Directory Structure

```
chatty/
+-- apps/
    +-- server/
        |-- pyproject.toml
        |-- app/
        |   |-- main.py
        |   |-- config.py
        |   |-- database.py
        |   |-- models.py
        |   |-- deps.py
        |   |-- sse.py
        |   |-- security.py
        |   |-- slash.py
        |   |-- routers/
        |   |   |-- auth.py
        |   |   |-- rooms.py
        |   |   |-- messages.py
        |   |   |-- moderation.py
        |   |   +-- admin.py
        |   +-- moderation/
        |       |-- enforcer.py
        |       |-- spam.py
        |       +-- filter.py
        |-- migrations/
        |   +-- 001_initial.sql
        +-- tests/
```

---

## DB Schema

```sql
CREATE TABLE IF NOT EXISTS users (
    id             TEXT PRIMARY KEY,
    email          TEXT UNIQUE NOT NULL,
    nickname       TEXT UNIQUE NOT NULL,
    password_hash  TEXT NOT NULL,
    is_admin       BOOLEAN NOT NULL DEFAULT FALSE,
    is_active      BOOLEAN NOT NULL DEFAULT FALSE,
    last_room_id   TEXT,                         -- for auto-join on reconnect
    token_version  INTEGER NOT NULL DEFAULT 0,
    created_at     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS rooms (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL DEFAULT 'chat',
    is_private      BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE if password-protected
    is_dm           BOOLEAN NOT NULL DEFAULT FALSE,
    password_hash   TEXT,                         -- NULL means public
    owner_id        TEXT NOT NULL,                -- current owner (transferable)
    description     TEXT NOT NULL DEFAULT '',
    llm_context     TEXT NOT NULL DEFAULT '',
    announcement    TEXT NOT NULL DEFAULT '',
    max_members     INTEGER,
    slow_mode_sec   INTEGER NOT NULL DEFAULT 0,
    game_server_url TEXT,
    created_by      TEXT NOT NULL,               -- original creator (immutable)
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL,
    deleted_at      REAL,
    FOREIGN KEY (owner_id)   REFERENCES users(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

-- Remaining tables (room_tags, room_attrs, room_members, room_seq,
-- room_read_state, messages, global_bans, room_bans,
-- room_mutes, reports, room_filters, global_filters) are unchanged
```

### Seed Rooms

```python
_DEFAULT_ROOMS = [
    ("waiting", "#waiting", "chat", "Waiting room -- default room for all users"),
    ("general", "#general", "chat", "General chat room for everyone"),
    ("random",  "#random",  "chat", "Free talk, no specific topic"),
]
```

The `waiting` room cannot be deleted (exempted from the empty-room auto-delete logic).

---

## API Endpoints

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Register with email + nickname + password |
| POST | `/auth/login` | Login -- returns JWT |
| POST | `/auth/logout` | Invalidate token (token_version++) |
| GET  | `/auth/me` | Get my info |

### Rooms

| Method | Path | Description | Permission |
|--------|------|-------------|------------|
| GET | `/rooms?q=&type=` | Room list (search by name/description) | All |
| POST | `/rooms` | Create room | All |
| GET | `/rooms/{id}` | Room details | All |
| PATCH | `/rooms/{id}` | Update room | Owner |
| DELETE | `/rooms/{id}` | Delete room | Owner |
| PUT | `/rooms/{id}/tags` | Replace tags | Owner |
| PUT | `/rooms/{id}/attrs` | Replace custom attributes | Owner |
| POST | `/rooms/{id}/members` | Add member | Owner |
| DELETE | `/rooms/{id}/members/{user_id}` | Remove member | Owner |
| GET | `/rooms/{id}/stream` | SSE stream (`?token=`) | All |
| GET | `/rooms/{id}/users` | Current connected users | All |
| POST | `/rooms/{id}/join` | Join room (includes password verification) | All |
| POST | `/rooms/{id}/leave` | Leave room -- empty room deletion, owner transfer | All |
| POST | `/rooms/{id}/owner` | Transfer ownership `{"user_id": "..."}` | Owner |

### Messages

| Method | Path | Description |
|--------|------|-------------|
| GET | `/rooms/{id}/messages?before=&since_seq=&limit=` | History |
| GET | `/rooms/{id}/messages/search?q=` | ILIKE substring search |
| POST | `/rooms/{id}/messages` | Send message (includes slash command handling) |
| PATCH | `/rooms/{id}/messages/{msg_id}` | Edit message (own messages only) |
| DELETE | `/rooms/{id}/messages/{msg_id}` | Delete message (own or owner) |
| POST | `/rooms/{id}/read` | Update read position |

### Users

| Method | Path | Description |
|--------|------|-------------|
| GET | `/users/me/last-room` | Get last joined room |
| PUT | `/users/me/last-room` | Save last room `{"room_id": "..."}` |

### Moderation

| Method | Path | Description | Permission |
|--------|------|-------------|------------|
| POST | `/rooms/{id}/bans` | Room ban | Room creator / Admin |
| DELETE | `/rooms/{id}/bans/{user_id}` | Remove room ban | Room creator / Admin |
| POST | `/rooms/{id}/mutes` | Room mute | Room creator / Admin |
| DELETE | `/rooms/{id}/mutes/{user_id}` | Remove room mute | Room creator / Admin |
| POST | `/rooms/{id}/filters` | Add room filter | Room creator / Admin |
| DELETE | `/rooms/{id}/filters/{filter_id}` | Remove room filter | Room creator / Admin |
| POST | `/reports` | Report | All |

### Admin

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/rooms/{id}/system-message` | Send system message |
| GET | `/admin/users` | All users list |
| DELETE | `/admin/users/{user_id}` | Delete user |
| POST | `/admin/bans` | Global ban |
| DELETE | `/admin/bans/{user_id}` | Remove global ban |
| GET | `/admin/reports` | Report list |
| PATCH | `/admin/reports/{id}` | Handle report |
| POST | `/admin/filters` | Add global filter |
| DELETE | `/admin/filters/{filter_id}` | Remove global filter |

---

## Slash Commands (`slash.py`)

| Command | Handled By | Action | Permission |
|---------|------------|--------|------------|
| `/me <action>` | Server | Save as `msg_type=action` | All |
| `/topic` | Server | Return `announcement` (response_only) | All |
| `/topic <content>` | Server | Update `announcement` | Owner |
| `/who` | Server | Return connected users list (response_only) | All |
| `/pass <nickname>` | Server | Transfer ownership -- `owner_changed` SSE | Owner |
| `/rooms` | Client | Switch to room list screen | -- |
| `/join <room>` | Client | Call `POST /rooms/{id}/join` | -- |
| `/leave` | Client | Call `POST /rooms/{id}/leave` | -- |
| `/create` | Client | Switch to room creation form | -- |

---

## SSE Event Types

```
message          # New message
message_updated  # Message edited
message_deleted  # Message deleted
user_joined      # User joined
user_left        # User left
owner_changed    # Owner changed {"new_owner": "nickname"}
room_updated     # Room info changed (announcement, etc.)
room_deleted     # Room deleted (includes empty-room auto-deletion)
system           # System announcement
kicked           # Existing session terminated on duplicate connection
banned           # Ban applied
muted            # Mute applied
unmuted          # Mute removed
```

---

## Room Join/Leave Logic

### Join (`POST /rooms/{id}/join`)

```
1. Check room exists
2. Check max_members (based on SSE connections)
3. If is_private (has password) -> verify password
4. Update users.last_room_id
5. Broadcast SSE user_joined
```

### Leave (`POST /rooms/{id}/leave`)

```
1. Broadcast SSE user_left
2. If owner:
   a. Other users connected -> auto-transfer to longest-connected user + owner_changed SSE
   b. No other users -> proceed to next step
3. If 0 connected users:
   a. If waiting room -> do not delete
   b. Otherwise -> soft delete + room_deleted SSE
4. Update users.last_room_id = "waiting"
```

---

## Owner System

- `rooms.owner_id`: Current owner (initial value = `created_by`)
- Owner permissions: room editing, announcement setting (`/topic`), ban/mute, ownership transfer (`/pass`)
- Auto-transfer criteria: the user who connected first among SSE connections (`_rooms[room_id]` insertion order)

---

## Moderation System

### Pre-send Message Inspection Pipeline

```
1. Check global ban
2. Check room ban
3. Check room mute
4. Check slow_mode (last message created_at vs slow_mode_sec for same user)
5. Global filter check
6. Room filter check
7. Auto spam detection
```

### Auto Spam Detection Rules

| Rule | Condition | Penalty |
|------|-----------|---------|
| Flooding | Same text 3+ times within 60 seconds | Room mute 10 min |
| Rapid repeat | 5+ messages within 5 seconds | Room mute 5 min |
| URL spam | 5+ messages containing URLs within 60 seconds | Room mute 30 min |

---

## Authentication Design

### JWT Structure

```python
{
  "sub": "user_id",
  "nickname": "player1",
  "is_admin": false,
  "token_version": 0,
  "exp": unix_timestamp  # 24 hours
}
```

### SSE Token Delivery

EventSource cannot send custom headers -- use `?token=` query param.

---

## Message Pagination

```
Initial load:          GET /rooms/{id}/messages?limit=50
Load older messages:   GET /rooms/{id}/messages?before={msg_id}&limit=50
Reconnection recovery: GET /rooms/{id}/messages?since_seq={seq}&limit=200
```

---

## Security

| Item | Approach |
|------|----------|
| Authentication | JWT Bearer token |
| SSE | `?token=` query param |
| Private rooms | bcrypt hash stored, verified on join |
| SQL injection | Parameter binding only (no f-string queries) |
| Rate limiting | In-memory, limits on POST /auth/* and message sending |
| JWT invalidation | `token_version` -- incremented on logout |

---

## Verification

```bash
# Start server
uv run uvicorn app.main:app --reload --port 7799 --app-dir apps/server

# Run tests
uv run pytest apps/server/tests/ -v
```
