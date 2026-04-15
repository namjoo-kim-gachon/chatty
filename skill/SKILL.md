---
name: chatty
description: Control a running Chatty TUI client. Use this skill when the user types /chatty with any subcommand (status, rooms, messages, users), or when the user asks to interact with a Chatty chat room — read/send messages, list/join/create/leave rooms, check who's online. Requires a Chatty TUI to be running with its socket server active.
---

# Chatty CLI

Control a running Chatty TUI client via TCP socket. The TUI must be running.

## CLI

```bash
CLI="bash ~/.claude/skills/chatty/scripts/chatty-cli.sh"
```

Set `CHATTY_SOCKET_PORT` env var if TUI uses a non-default port (default: 7800).

## Commands

Parse `/chatty <args>` and run the matching command. All output is JSON.

### status

```bash
$CLI status
```

Returns: `{ nickname, user_id, is_admin, active_room, sse_status, is_muted, is_banned }`

### rooms list

```bash
$CLI rooms list [--query <search>]
```

Returns: `Room[]` with `id, name, type, description, is_private, owner_nickname`

### rooms create

```bash
$CLI rooms create --name <name> [--description <d>] [--password <p>] [--max-members <n>] [--slow-mode <sec>]
```

### rooms join

```bash
$CLI rooms join <room-id> [--password <p>]
```

Switches the TUI's active room.

### rooms leave

```bash
$CLI rooms leave
```

TUI returns to #waiting.

### rooms info

```bash
$CLI rooms info
```

### messages list

```bash
$CLI messages list [--limit <n>]
```

Returns last N messages (default 50) from TUI memory. Each: `{ id, nickname, text, msg_type, seq, created_at }`

### messages send

```bash
$CLI messages send <text>
```

### users list

```bash
$CLI users list
```

Returns: `string[]` of nicknames.

## Error Handling

- Exit code 1 + stderr = failure
- "Cannot connect to Chatty TUI" = TUI not running or wrong port
- "Not connected to any room" = no active room
- "TUI not ready" = TUI running but not logged in yet
