# chatty

[![npm](https://img.shields.io/npm/v/@namjookim/chatty)](https://www.npmjs.com/package/@namjookim/chatty)
[![node](https://img.shields.io/node/v/@namjookim/chatty)](https://nodejs.org)
[![license](https://img.shields.io/github/license/namjoo-kim-gachon/chatty)](LICENSE)

Real-time terminal chat — React/Ink TUI + CLI remote control

```
┌─ #lobby ──────────────────────────────────────────────────┐
│ alice   hey everyone!                                     │
│ bob     hi alice :)                                       │
│ alice   nice weather today                                │
├───────────────────────────────────────────────────────────┤
│ > _                                                       │
└───────────────────────────────────────────────────────────┘
```

## Features

- **Multi-room chat** — public/private/password-protected rooms, jump by room number (#1, #2…)
- **Google OAuth** — sign in with Google, no account creation needed
- **Real-time streaming** — instant delivery via SSE (Server-Sent Events)
- **Moderation** — slow mode, mute, ban, word filters, reports
- **chatty-cli** — remote-control a running TUI from scripts or other processes
- **Claude Code integration** — chatty skill lets Claude read and send messages in chat rooms
- **Multilingual** — auto-detects system locale

---

## Quick Start

A public server is available at [chatty.1000.school](https://chatty.1000.school).

```bash
npm install -g @namjookim/chatty
chatty
```

On first run, a browser window opens for Google sign-in. Once authenticated, you're in.

---

## Installation & Commands

```bash
# Install globally
npm install -g @namjookim/chatty

# Launch TUI
chatty

# Sign in separately
chatty login

# Change nickname
chatty nickname
```

---

## Slash Commands (inside TUI)

| Command | Description |
|---------|-------------|
| `/rooms` | List available rooms |
| `/join <number>` | Join a room by number |
| `/leave` | Leave the current room |
| `/create <name>` | Create a new room |
| `/who` | List users in the current room |
| `/mute <nickname>` | Mute a user (owner only) |
| `/unmute <nickname>` | Unmute a user (owner only) |
| `/ban <nickname>` | Ban a user (owner only) |
| `/unban <nickname>` | Unban a user (owner only) |
| `/?` | Show available commands |
| `/quit` | Quit the TUI |

---

## chatty-cli

Controls a running TUI instance over a local TCP socket (default port 7800).  
Useful for scripting, automation, and Claude Code integration.

```bash
# Current status
chatty-cli status

# List / search rooms
chatty-cli rooms list
chatty-cli rooms list --query "game"

# Join / leave / info
chatty-cli rooms join 3
chatty-cli rooms leave
chatty-cli rooms info

# Create a room
chatty-cli rooms create --name "my room" --description "..." --max-members 50

# Read / send messages
chatty-cli messages list --limit 20
chatty-cli messages list --all
chatty-cli messages send "hello"

# Users & moderation
chatty-cli users list
chatty-cli users mute <nickname>
chatty-cli users unmute <nickname>
chatty-cli users ban <nickname>
chatty-cli users unban <nickname>

# Human-readable output
chatty-cli --pretty rooms list
```

Change socket port: `CHATTY_SOCKET_PORT=7801 chatty-cli status`

---

## Configuration

`~/.config/chatty/config.json` is created automatically on first run.

```json
{
  "server_url": "https://chatty.1000.school",
  "theme": "default",
  "locale": "en",
  "keybindings": {
    "scroll_up": "pageup",
    "scroll_down": "pagedown",
    "scroll_bottom": "end"
  },
  "reconnect": {
    "max_attempts": 10,
    "base_delay_ms": 1000,
    "max_delay_ms": 30000
  }
}
```

| Environment variable | Description | Default |
|----------------------|-------------|---------|
| `CHATTY_SERVER_URL` | Server URL | `https://chatty.1000.school` |
| `CHATTY_CONFIG` | Config file path | `~/.config/chatty/config.json` |
| `CHATTY_SOCKET_PORT` | CLI socket port | `7800` |

---

## Self-hosting

### Requirements

- Python 3.12+, [uv](https://docs.astral.sh/uv/)
- PostgreSQL
- Redis

### Setup

```bash
git clone https://github.com/namjoo-kim-gachon/chatty.git
cd chatty

# Configure environment
cp .env.example .env
# Edit .env

# Start the server
uv run uvicorn app.main:app --port 7799 --app-dir apps/server
```

### `.env` reference

| Variable | Description |
|----------|-------------|
| `CHATTY_DATABASE_URL` | PostgreSQL connection string |
| `CHATTY_REDIS_URL` | Redis URL |
| `CHATTY_SECRET_KEY` | JWT signing key — **change this in production** |
| `CHATTY_GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `CHATTY_GOOGLE_CLIENT_SECRET` | Google OAuth secret |
| `CHATTY_BASE_URL` | Base URL for OAuth redirect (e.g. `https://your-domain.com`) |

Get OAuth credentials from [Google Cloud Console](https://console.cloud.google.com/).  
Redirect URI: `{CHATTY_BASE_URL}/auth/google/callback`

### Connecting the client to your server

```bash
CHATTY_SERVER_URL=http://localhost:7799 chatty
```

Or set `server_url` in `~/.config/chatty/config.json`.

---

## Development

```bash
# Install client dependencies
cd apps/client && npm install

# Run TUI in dev mode
npm run dev

# Run server in dev mode
uv run uvicorn app.main:app --reload --port 7799 --app-dir apps/server

# Tests
uv run pytest apps/server/tests/ -v    # server
npm test --workspace apps/client        # client
```

---

## Using chatty with AI Agents

Copy and paste the prompt below into Claude Code, Codex, Gemini, or any other AI agent to give it the ability to interact with a running chatty TUI.

> **Prerequisite:** The chatty TUI must already be running (`chatty`) before the agent can connect.

````markdown
## chatty-cli — control a running Chatty TUI

A Chatty TUI is running on this machine. You can control it via `chatty-cli`.

### Setup (if not already installed)
```bash
npm install -g @namjookim/chatty
```

### Read state
```bash
chatty-cli status                          # who am I, which room, connection status
chatty-cli rooms list                      # all available rooms
chatty-cli rooms list --query <keyword>    # search rooms
chatty-cli rooms info                      # current room details
chatty-cli messages list                   # last 50 messages
chatty-cli messages list --limit <n>       # last N messages
chatty-cli messages list --all             # all messages in TUI memory
chatty-cli users list                      # users in current room
```

### Take action
```bash
chatty-cli rooms join <room-number>        # switch to a room (number, not ID)
chatty-cli rooms leave                     # return to lobby
chatty-cli rooms create --name <name>      # create a new room
chatty-cli messages send <text>            # send a message to the current room
chatty-cli users mute <nickname>           # mute a user (owner only)
chatty-cli users unmute <nickname>         # unmute a user (owner only)
chatty-cli users ban <nickname>            # ban a user (owner only)
chatty-cli users unban <nickname>          # unban a user (owner only)
```

### Output format
All commands output JSON by default. Add `--pretty` for human-readable output.

### Error handling
- Exit code 1 + stderr message = failure
- `"Cannot connect to Chatty TUI"` → TUI is not running or wrong port
- `"Not connected to any room"` → join a room first
- `"TUI not ready"` → TUI is running but not logged in yet

### Socket port
Default port is 7800. Override with: `CHATTY_SOCKET_PORT=<port> chatty-cli <command>`
````

---

## License

MIT
