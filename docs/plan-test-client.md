# Chatty Client -- E2E Test Plan

## Strategy

**Run the actual TUI process in a detached tmux session**.
Assumes the server (localhost:7799) is already running.
No manual verification -- all checks are done via screen output parsing.

```
vitest (test runner)
  +-- TmuxHarness (tmux session wrapper)
       |-- send-keys -l (literal text input)
       |-- send-keys (special key input)
       |-- capture-pane -p (plain text extraction)
       |-- capture-pane -p -e (ANSI color extraction)
       |-- resize-window (terminal resize)
  +-- ApiClient (direct HTTP calls)  <- test state setup
```

---

## Packages

No native dependencies required. tmux must be installed on the host machine.

```bash
# macOS
brew install tmux

# Verify
tmux -V
```

vitest was already installed in Phase 1.

---

## Directory Structure

```
apps/client/
+-- tests/
    |-- global-setup.ts      <- server health check (once)
    |-- setup.ts             <- (empty, no special error suppression needed)
    |-- helpers/
    |   |-- harness.ts       <- TmuxHarness: tmux session wrapper
    |   |-- api.ts           <- HTTP API wrapper (for test state setup)
    |   |-- server.ts        <- server start/stop (for reconnection tests)
    |   +-- fixtures.ts      <- test user/room creation helpers
    |-- login.e2e.ts
    |-- chat.e2e.ts
    |-- rooms.e2e.ts
    |-- sse-events.e2e.ts
    +-- game.e2e.ts
```

---

## helpers/harness.ts

Uses tmux instead of node-pty. Each test gets a unique detached tmux session.
tmux `capture-pane -p` returns plain text (no ANSI) automatically -- no need for `strip-ansi`.

```typescript
import { execSync } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"

const TMUX_KEYS: Record<string, string> = {
  enter: "Enter", tab: "Tab", shiftTab: "BTab", ctrlC: "C-c",
  ctrlR: "C-r", pageUp: "PPage", pageDown: "NPage", end: "End",
  up: "Up", down: "Down", escape: "Escape",
}
export type SpecialKey = keyof typeof TMUX_KEYS

let sessionCounter = 0

export class TmuxHarness {
  private readonly session: string
  readonly cols: number
  readonly rows: number

  constructor(configPath: string, { cols = 120, rows = 30 } = {}) {
    // Creates detached tmux session running the client
    execSync(`tmux new-session -d -s '${session}' -x ${cols} -y ${rows} "..."`,
      { cwd: CLIENT_ROOT })
  }

  screen(): string {
    // capture-pane -p without -e strips ANSI automatically
    return execSync(`tmux capture-pane -t '${this.session}' -p -S -`, { encoding: "utf8" })
  }

  screenAnsi(): string {
    // with -e flag for color assertions
    return execSync(`tmux capture-pane -t '${this.session}' -p -e -S -`, { encoding: "utf8" })
  }

  async waitFor(predicate, timeout = 5000): Promise<void> { /* polls screen() every 100ms */ }
  async waitForText(text, timeout = 10_000): Promise<void> { /* calls waitFor */ }
  type(text: string): void { execSync(`tmux send-keys -t '${session}' -l '${text}'`) }
  press(key: SpecialKey): void { execSync(`tmux send-keys -t '${session}' ${mapped}`) }
  resize(cols, rows): void { execSync(`tmux resize-window -t '${session}' -x ${cols} -y ${rows}`) }
  clearBuffer(): void { execSync(`tmux clear-history -t '${session}'`) }
  async kill(): Promise<void> { execSync(`tmux kill-session -t '${session}'`) }
}
```

### Key Differences from node-pty

| Feature | node-pty | tmux |
|---------|----------|------|
| ANSI stripping | Required `strip-ansi` package | `capture-pane -p` strips automatically |
| Native compilation | Required (C++ addon, platform-specific) | No native deps, just `tmux` binary |
| Screen capture | Accumulated buffer (all output since start) | Current visible pane content |
| Terminal resize | `pty.resize(cols, rows)` | `tmux resize-window -x cols -y rows` |
| ANSI output | Not easily accessible | `capture-pane -p -e` preserves ANSI |
| Scrollback clear | `buffer = ""` | `tmux clear-history` |

---

## helpers/api.ts

HTTP client for test setup. Manipulates server state directly without going through the TUI.

Key functions: `register()`, `login()`, `sendMessage()`, `editMessage()`, `deleteMessage()`, `banUser()`, `muteUser()`, `createAdminUser()` (via psql).

---

## helpers/server.ts

Controls the server process for reconnection tests.
Used only in `sse-events.e2e.ts`.

Key functions: `stopServer()`, `startServer()`, `restartServer()`.

---

## helpers/fixtures.ts

```typescript
export async function createTestUser(prefix = "u"): Promise<TestUser>
export async function createAdminTestUser(prefix = "admin"): Promise<TestUser>
export function createConfig(user: TestUser, overrides?: Record<string, unknown>): string
export async function loginTui(tui: TmuxHarness, password: string): Promise<void>
```

`loginTui` waits for `"password:"`, types the password, presses enter, then waits for `"* connected"`.

---

## Test Cases

### login.e2e.ts

| Test | Steps | Expected |
|------|-------|----------|
| Correct credentials | Type password -> Enter | `#general` and nickname visible |
| Wrong password | Type wrong password -> Enter | `"Login failed"` displayed |

### chat.e2e.ts

| Test | Steps | Expected |
|------|-------|----------|
| Send message | Type "Hello world" -> Enter | Message and nickname visible |
| SSE receive | Sender sends via API | Message appears in viewer TUI |
| Message edit | Edit via API | Updated text + `"(edited)"` |
| Message delete | Delete via API | `"[deleted]"` displayed |

### rooms.e2e.ts

| Test | Steps | Expected |
|------|-------|----------|
| Room switch | Ctrl+R | `#mud` tab appears |
| Preserve messages | Switch rooms | Previous room messages not shown |

### sse-events.e2e.ts

| Test | Steps | Expected |
|------|-------|----------|
| Muted | Admin mutes user | `"[muted]"` displayed |
| Banned | Admin bans user | `"banned"` displayed |
| Reconnect | Stop/start server | Missed messages recovered |
| Kicked | Open second SSE connection | Reconnect behavior |

### game.e2e.ts

| Test | Steps | Expected |
|------|-------|----------|
| Command input | Type "look" -> Enter | `"look"` echoed |
| Shortcut expansion | Type "l" -> Enter | Expanded to `"look"` |
| Command history | Up key | Previous command recalled |

---

## Running Tests

```bash
# Start server first
uv run uvicorn app.main:app --reload --port 7799 --app-dir apps/server

# Run all e2e tests
npm run test --filter=@chatty/client

# Run specific file only
npx vitest run tests/chat.e2e.ts
```

---

## Notes

| Item | Details |
|------|---------|
| Test isolation | Users are always created uniquely with `Date.now() + counter` suffix |
| Timeouts | `waitForText` defaults to 10 seconds, `waitFor` defaults to 5 seconds |
| Terminal size | Default `cols: 120, rows: 30` -- large enough to prevent line wrapping |
| ANSI | `capture-pane -p` strips ANSI automatically; use `screenAnsi()` for color assertions |
| Parallel execution | vitest default parallel execution works (each test gets unique tmux session) |
| Prerequisite | tmux must be installed on the host machine |
