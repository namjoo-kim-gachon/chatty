---
name: chatty
description: Control a running Chatty TUI client. Use this skill when the user types /chatty with any subcommand (status, rooms, messages, users), or when the user asks to interact with a Chatty chat room — read/send messages, list/join/create/leave rooms, check who's online. Requires a Chatty TUI to be running with its socket server active.
---

# Chatty CLI

Control a running Chatty TUI client via TCP socket.

## Setup

If `chatty-cli` is not installed, run:
```bash
npm install -g @namjookim/chatty
```

The chatty TUI must already be running (`chatty`) before you can connect.

Set `CHATTY_SOCKET_PORT` env var if TUI uses a non-default port (default: 7800).

## Commands

Parse `/chatty <args>` and run the matching `chatty-cli` command. All output is JSON.

### status

```bash
chatty-cli status
```

Returns: `{ nickname, user_id, is_admin, active_room, sse_status, is_muted, is_banned }`

### rooms list

```bash
chatty-cli rooms list [--query <search>]
```

Returns: `Room[]` with `id, name, type, description, is_private, owner_nickname`

### rooms create

```bash
chatty-cli rooms create --name <name> [--description <d>] [--password <p>] [--max-members <n>] [--slow-mode <sec>]
```

### rooms join

```bash
chatty-cli rooms join <room-number> [--password <p>]
```

Switches the TUI's active room.

### rooms leave

```bash
chatty-cli rooms leave
```

### rooms info

```bash
chatty-cli rooms info
```

### messages list

```bash
chatty-cli messages list [--limit <n>] [--all]
```

Returns last N messages (default 50) from TUI memory. Each: `{ id, nickname, text, msg_type, seq, created_at }`

### messages send

```bash
chatty-cli messages send <text>
```

### users list

```bash
chatty-cli users list
```

Returns: `string[]` of nicknames.

### users mute / unmute / ban / unban

```bash
chatty-cli users mute <nickname>
chatty-cli users unmute <nickname>
chatty-cli users ban <nickname>
chatty-cli users unban <nickname>
```

Owner only.

## Error Handling

- Exit code 1 + stderr = failure
- "Cannot connect to Chatty TUI" = TUI not running or wrong port
- "Not connected to any room" = no active room
- "TUI not ready" = TUI running but not logged in yet
