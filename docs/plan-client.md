# Chatty Client -- Implementation Plan

## Overview

**Location**: `/Users/namjookim/projects/chatty/apps/client/`  
**Tech Stack**: Node.js + TypeScript (strict) + Ink 5 (React-based TUI)  
**Role**: Terminal chat client

---

## User Flow

```
App launch
  -> Load ~/.config/chatty/config.json
  -> Login prompt (password input)
  -> GET /users/me/last-room
      -> If last room exists, auto-join
      -> If not, join waiting room (#waiting)
  -> Chat screen

Slash commands:
  /rooms     -> Room list screen
  /join <rm> -> Direct join (shows password input if private)
  /leave     -> Return to waiting room (from waiting room -> exit program)
  /create    -> Room creation form screen
  /who       -> Connected users list screen
  /topic     -> Print announcement in chat area
  /me <action> -> Send action message
  /pass <nick> -> Transfer ownership
```

---

## Screen States

The app displays one of the following screens.

```typescript
type Screen =
  | { type: "chat" }
  | { type: "room_list" }
  | { type: "user_list" }
  | { type: "create_room" }
  | { type: "password_input"; roomId: string; roomName: string }
```

---

## UI Layout

### Chat Screen

```
----------------------------------------------------
12:34  alice       Hello
12:35  bob         Nice to meet you
12:36  ***         System message
12:37  * alice     dances
----------------------------------------------------
[player1] _
----------------------------------------------------
#general  3 users  * connected  player1  [owner: alice]
```

### Room List Screen (`/rooms`)

```
----------------------------------------------------
  Room List  Search: _
----------------------------------------------------
> #general        chat  3 users  General chat room for everyone
  #random         chat  1 user   Free talk, no specific topic
  lock #secret    chat  2 users  Secret room
----------------------------------------------------
Up/Down select  Enter join  Esc cancel
```

### Connected Users Screen (`/who`)

```
----------------------------------------------------
  #general connected users (3)
----------------------------------------------------
  * alice  (owner)
    bob
    charlie
----------------------------------------------------
Esc close
```

### Room Creation Form (`/create`)

```
----------------------------------------------------
  Create Room
----------------------------------------------------
  Name     : _
  Desc     :
  Password :
  Max users:
  Slow mode: 0 sec
----------------------------------------------------
Tab next  Enter create  Esc cancel
```

### Password Input Screen

```
----------------------------------------------------
  lock #secret join
----------------------------------------------------
  Password: _
----------------------------------------------------
Enter confirm  Esc cancel
```

---

## Keyboard Shortcuts

### Chat Screen

| Key | Action |
|-----|--------|
| `PageUp` | Scroll up |
| `PageDown` | Scroll down |
| `End` | Jump to bottom |
| `Ctrl+C` | Exit (logout then exit) |

### Room List Screen

| Key | Action |
|-----|--------|
| `Up` / `Down` | Select room |
| Typing | Real-time search filter |
| `Enter` | Join |
| `Esc` | Return to chat |

### Connected Users Screen

| Key | Action |
|-----|--------|
| `Esc` | Return to chat |

### Room Creation Form

| Key | Action |
|-----|--------|
| `Tab` | Next field |
| `Shift+Tab` | Previous field |
| `Enter` | Create |
| `Esc` | Cancel |

---

## Directory Structure

```
apps/client/src/
|-- index.tsx              # Login -> Root
|-- app.tsx                # Screen state router
|-- types.ts
|-- config.ts
|-- lib/
|   |-- auth.ts            # login, logout
|   |-- client.ts          # REST API calls
|   +-- sse.ts             # SSE connection + reconnection
|-- components/
|   |-- Separator.tsx
|   |-- MessageList.tsx
|   |-- InputBar.tsx
|   |-- StatusBar.tsx
|   |-- RoomListScreen.tsx  # /rooms screen
|   |-- UserListScreen.tsx  # /who screen
|   |-- CreateRoomForm.tsx  # /create screen
|   +-- PasswordInput.tsx   # Password input screen
+-- hooks/
    |-- useChat.ts          # Current room chat state
    |-- useScroll.ts
    |-- useKeyBindings.ts
    +-- useCommandHistory.ts
```

---

## Shared Types (`src/types.ts`)

```typescript
export type RoomType = "chat" | "game"
export type MessageType = "chat" | "action" | "system" | "game_response" | "game_command"
export type SSEStatus = "connected" | "reconnecting" | "disconnected"

export type Screen =
  | { type: "chat" }
  | { type: "room_list" }
  | { type: "user_list" }
  | { type: "create_room" }
  | { type: "password_input"; roomId: string; roomName: string }

export interface Room {
  id: string
  name: string
  type: RoomType
  description: string
  is_private: boolean   // has password
  max_members: number | null
  slow_mode_sec: number
  owner_nickname: string
  user_count: number
}

export interface Message {
  id: string
  room_id: string
  nickname: string
  text: string
  msg_type: MessageType
  seq: number
  created_at: number
  edited_at?: number
  deleted_at?: number
}

export interface Config {
  email: string
  server_url: string
  keybindings: Record<string, string>
  reconnect: {
    max_attempts: number
    base_delay_ms: number
    max_delay_ms: number
  }
}

export interface AuthState {
  token: string
  user_id: string
  nickname: string
  is_admin: boolean
}
```

---

## Slash Command Handling

When Enter is pressed in `InputBar`, if text starts with `/`, it is first processed as a client command.  
If it is not a client command, it is sent to `POST /rooms/{id}/messages` (server handles `/me`, `/topic`, `/who`, `/pass`).

```typescript
function handleCommand(text: string, ctx: CommandContext): boolean {
  const [cmd, ...args] = text.split(" ")
  switch (cmd) {
    case "/rooms":  setScreen({ type: "room_list" }); return true
    case "/create": setScreen({ type: "create_room" }); return true
    case "/who":    setScreen({ type: "user_list" }); return true
    case "/leave":  handleLeave(); return true
    case "/join":   handleJoin(args[0]); return true
    default:        return false  // send to server
  }
}
```

---

## Reconnection Logic

```
App start -> GET /users/me/last-room
  -> If room_id exists -> POST /rooms/{id}/join
      -> Success: enter that room's chat screen
      -> Failure (deleted/missing): POST /rooms/waiting/join
  -> If no room_id -> POST /rooms/waiting/join
```

Exponential backoff reconnection on SSE disconnect:
- base: `config.reconnect.base_delay_ms` (1 second)
- max: `config.reconnect.max_delay_ms` (30 seconds)
- max attempts: `config.reconnect.max_attempts` (10)
- On successful reconnection -> recover missed messages via `since_seq`

---

## SSE Event Handling

| Event | Handling |
|-------|----------|
| `message` | Append message, update lastSeq |
| `message_updated` | Replace text |
| `message_deleted` | Replace with `[deleted message]` |
| `user_joined` | User count +1 |
| `user_left` | User count -1 |
| `owner_changed` | Update owner nickname |
| `room_deleted` | Show system message then move to waiting room |
| `room_updated` | Update room info |
| `kicked` | Reconnect SSE after 1 second |
| `banned` | Block input, close SSE |
| `muted` / `unmuted` | Disable/enable input |
| `system` | Display as system message |

---

## Message Type Rendering

| msg_type | Color | Nickname Column |
|----------|-------|-----------------|
| `chat` | white | `nickname` (nick-color, 12-char padding) |
| `action` | cyan | `* nickname` |
| `system` | yellow | `***` |
| `game_response` | green | `>>>` |
| `game_command` | dim | ` > ` |

- `HH:mm` timestamp (dimColor)
- Edited message: `(edited)` dim at end of line
- Deleted message: `[deleted message]` dim

---

## config.json

```json
{
  "email": "player1@example.com",
  "server_url": "http://localhost:7799",
  "keybindings": {
    "scroll_up":     "pageup",
    "scroll_down":   "pagedown",
    "scroll_bottom": "end"
  },
  "reconnect": {
    "max_attempts":  10,
    "base_delay_ms": 1000,
    "max_delay_ms":  30000
  }
}
```

Location: `~/.config/chatty/config.json` (auto-created with defaults if missing)  
Passwords and JWTs are not stored -- login is required on every launch.

---

## Verification

```bash
npm run dev     # server must be running first
npm run check   # typecheck + lint + format
```
