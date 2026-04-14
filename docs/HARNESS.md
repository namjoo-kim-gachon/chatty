# Chatty -- Harness Design

> Based on Anthropic Engineering: "Harness design for long-running application development" (2026-03-24)

---

## Core Principles

1. **Generator-Evaluator Separation** -- Models tend to praise their own code. Set up a separate evaluator configured to be skeptical.
2. **Sprint Contract** -- Before implementation, specify "done criteria" as hard thresholds. No ambiguous criteria allowed.
3. **Incremental Progress** -- Only one Phase at a time. Must commit before context is exhausted.
4. **Artifact-Based Handoff** -- State between sessions is passed via files. No reliance on conversation context.
5. **Active QA** -- The evaluator interacts directly with the running system. Reading code alone is insufficient.

---

## Harness Structure

```
[Initializer]  Once at start -- environment setup + feature list generation
      |
      v
[Sprint Contract]  Before Phase start -- negotiate done criteria
      |
      v
[Generator]  Implement one Phase (one file at a time)
      |
      v
[Evaluator]  turbo check + API tests + smoke tests
      |
      v
Pass -> Sprint Contract check -> Next Phase
Fail -> Write feedback file -> Re-deliver to Generator
```

---

## Initializer (Once at Start)

Must run first when starting a new session:

```bash
# 1. Verify working directory
pwd   # Must be /Users/namjookim/projects/chatty

# 2. Assess current state
cat docs/progress.md          # Previous session progress
cat docs/features.json        # Full feature list + status
git log --oneline -10         # Recent commit history

# 3. Start dev server
bash scripts/init.sh

# 4. Pre-startup basic test (if server exists)
curl -s http://localhost:7799/health
```

---

## Sprint Contract Format

Written in `docs/sprint.md` **before** Phase start. No changes during implementation.

```markdown
## Sprint N -- [Phase Name]

### Scope (this only)
- [ ] Item to implement 1 (specify filename)
- [ ] Item to implement 2 (specify filename)

### Done Criteria (hard threshold -- all must pass to be complete)
- [ ] `turbo check` 0 errors
- [ ] `uv run pytest tests/test_xxx.py` all pass
- [ ] All curl scenarios return 200
- [ ] [Phase-specific behavioral criteria -- be specific]

### Out of Scope (absolutely do not)
- No writing code for the next Phase in advance
- No modifying already-passing tests
```

---

## Generator Rules

1. Write **only one file at a time**, verify `turbo check` passes, then move to the next file
2. If context grows long during implementation, immediately commit and update `docs/progress.md`
3. If a type error occurs, it must be resolved before moving to the next file
4. Absolutely no `any` type, `// @ts-ignore`, or `# type: ignore`
5. Before declaring a feature complete, self-run `turbo check` + related tests

---

## Evaluator Checklist

### Server (apps/server)

```bash
# 1. Static analysis
turbo check --filter=@chatty/server
# == uv run ruff check + ruff format --check + basedpyright

# 2. Unit/integration tests
uv run pytest tests/ -v --tb=short

# 3. API smoke test (after server startup)
bash scripts/smoke-test-server.sh
```

### Client (apps/client)

```bash
# 1. Static analysis
turbo check --filter=@chatty/client
# == tsc --noEmit + eslint + prettier --check

# 2. Startup test
npm run dev --workspace=apps/client
# -> Verify TUI renders without crashing
```

### Evaluation Criteria (applied skeptically by Evaluator)

| Criterion | Pass Condition | On Failure |
|-----------|----------------|------------|
| Type safety | `turbo check` 0 errors | Send error list to Generator |
| Tests | All tests pass | Send failing tests + stack traces |
| API behavior | All curl scenarios return 2xx | Send failed response bodies |
| Code quality | No ruff/eslint violations | Send violation list + fix direction |
| Scope compliance | No code outside Sprint Contract scope | Send list of out-of-scope files |

---

## Cross-Session State Management

### docs/progress.md Format

Must be updated before ending a session:

```markdown
## [Date] Sprint N -- [Phase Name]

### Completed
- [x] apps/server/app/database.py -- SQLite connection, init_db()
- [x] apps/server/migrations/001_initial.sql

### Incomplete / Continue in Next Session
- [ ] apps/server/app/security.py -- JWT generation/verification in progress

### Issues / Notes
- SQLite thread issue when calling init_db() in FastAPI lifespan -> check_same_thread=False needed

### Next Session Starting Point
Start writing apps/server/app/security.py. Using bcrypt + python-jose.
```

### docs/features.json

Full feature list. AI modifies JSON less arbitrarily than Markdown.

```json
{
  "server": {
    "auth": {
      "register":       { "status": "failing", "sprint": 2, "endpoint": "POST /auth/register" },
      "login":          { "status": "failing", "sprint": 2, "endpoint": "POST /auth/login" },
      "me":             { "status": "failing", "sprint": 2, "endpoint": "GET /auth/me" },
      "logout":         { "status": "failing", "sprint": 2, "endpoint": "POST /auth/logout" }
    },
    "rooms": {
      "list":           { "status": "failing", "sprint": 3, "endpoint": "GET /rooms" },
      "create":         { "status": "failing", "sprint": 3, "endpoint": "POST /rooms" },
      "get":            { "status": "failing", "sprint": 3, "endpoint": "GET /rooms/{id}" },
      "update":         { "status": "failing", "sprint": 3, "endpoint": "PATCH /rooms/{id}" },
      "delete":         { "status": "failing", "sprint": 3, "endpoint": "DELETE /rooms/{id}" },
      "sse_stream":     { "status": "failing", "sprint": 3, "endpoint": "GET /rooms/{id}/stream" },
      "users":          { "status": "failing", "sprint": 3, "endpoint": "GET /rooms/{id}/users" },
      "tags":           { "status": "failing", "sprint": 3, "endpoint": "PUT /rooms/{id}/tags" },
      "attrs":          { "status": "failing", "sprint": 3, "endpoint": "PUT /rooms/{id}/attrs" }
    },
    "messages": {
      "history":        { "status": "failing", "sprint": 4, "endpoint": "GET /rooms/{id}/messages" },
      "send":           { "status": "failing", "sprint": 4, "endpoint": "POST /rooms/{id}/messages" },
      "edit":           { "status": "failing", "sprint": 4, "endpoint": "PATCH /rooms/{id}/messages/{mid}" },
      "delete":         { "status": "failing", "sprint": 4, "endpoint": "DELETE /rooms/{id}/messages/{mid}" },
      "search":         { "status": "failing", "sprint": 4, "endpoint": "GET /rooms/{id}/messages/search" },
      "read":           { "status": "failing", "sprint": 4, "endpoint": "POST /rooms/{id}/read" }
    },
    "dm": {
      "start":          { "status": "failing", "sprint": 5, "endpoint": "POST /dm" },
      "list":           { "status": "failing", "sprint": 5, "endpoint": "GET /dm" }
    },
    "moderation": {
      "ban_room":       { "status": "failing", "sprint": 6, "endpoint": "POST /rooms/{id}/bans" },
      "mute_room":      { "status": "failing", "sprint": 6, "endpoint": "POST /rooms/{id}/mutes" },
      "filter_room":    { "status": "failing", "sprint": 6, "endpoint": "POST /rooms/{id}/filters" },
      "report":         { "status": "failing", "sprint": 6, "endpoint": "POST /reports" },
      "spam_detect":    { "status": "failing", "sprint": 6, "endpoint": "auto" }
    },
    "bots": {
      "create":         { "status": "failing", "sprint": 6, "endpoint": "POST /bots" },
      "token_issue":    { "status": "failing", "sprint": 6, "endpoint": "POST /bots/{id}/tokens" }
    },
    "admin": {
      "system_msg":     { "status": "failing", "sprint": 7, "endpoint": "POST /admin/rooms/{id}/system-message" },
      "global_ban":     { "status": "failing", "sprint": 7, "endpoint": "POST /admin/bans" },
      "reports":        { "status": "failing", "sprint": 7, "endpoint": "GET /admin/reports" }
    }
  },
  "client": {
    "config": {
      "load":           { "status": "failing", "phase": 2 },
      "default_create": { "status": "failing", "phase": 2 }
    },
    "api": {
      "fetch_rooms":    { "status": "failing", "phase": 3 },
      "send_message":   { "status": "failing", "phase": 3 },
      "send_command":   { "status": "failing", "phase": 3 },
      "sse_connect":    { "status": "failing", "phase": 3 },
      "sse_reconnect":  { "status": "failing", "phase": 10 }
    },
    "ui": {
      "room_tabs":      { "status": "failing", "phase": 7 },
      "message_list":   { "status": "failing", "phase": 4 },
      "input_bar":      { "status": "failing", "phase": 5 },
      "status_bar":     { "status": "failing", "phase": 6 },
      "scroll":         { "status": "failing", "phase": 8 },
      "room_switch":    { "status": "failing", "phase": 9 },
      "unread_count":   { "status": "failing", "phase": 9 },
      "dm_tab":         { "status": "failing", "phase": 9 }
    },
    "slash_commands": {
      "me":             { "status": "failing", "phase": 11 },
      "join":           { "status": "failing", "phase": 11 },
      "msg":            { "status": "failing", "phase": 11 },
      "who":            { "status": "failing", "phase": 11 }
    },
    "game": {
      "game_prompt":    { "status": "failing", "phase": 12 },
      "cmd_history":    { "status": "failing", "phase": 12 },
      "cmd_shortcut":   { "status": "failing", "phase": 12 }
    }
  }
}
```

---

## scripts/init.sh

```bash
#!/usr/bin/env bash
# chatty dev environment startup script
# Always run this first when starting a session

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== chatty dev environment ==="
echo "Root: $ROOT"

# Install Python dependencies
echo "[1/3] Installing Python dependencies..."
uv sync

# Install Node.js dependencies
echo "[2/3] Installing Node.js dependencies..."
npm install

# Start server (background)
echo "[3/3] Starting server..."
uv run --package chatty-server uvicorn app.main:app \
  --reload \
  --port 7799 \
  --app-dir apps/server &

SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# Wait for server ready (max 10 seconds)
for i in $(seq 1 10); do
  if curl -sf http://localhost:7799/health > /dev/null 2>&1; then
    echo "Server ready at http://localhost:7799"
    break
  fi
  sleep 1
done

echo ""
echo "=== Ready ==="
echo "Server:  http://localhost:7799"
echo "Docs:    http://localhost:7799/docs"
echo ""
echo "To stop server: kill $SERVER_PID"
```

---

## scripts/smoke-test-server.sh

Curl scenarios used by the Evaluator to verify API behavior. Used as Sprint done criteria.

```bash
#!/usr/bin/env bash
# Server API smoke test
set -euo pipefail

BASE="http://localhost:7799"
PASS=0
FAIL=0

check() {
  local name="$1"
  local status="$2"
  local expected="$3"
  if [ "$status" -eq "$expected" ]; then
    echo "PASS $name"
    ((PASS++))
  else
    echo "FAIL $name (got $status, expected $expected)"
    ((FAIL++))
  fi
}

# Health check
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/health")
check "GET /health" "$STATUS" 200

# Authentication
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"email":"smoke@test.com","nickname":"smoketest","password":"pass1234"}')
check "POST /auth/register" "$STATUS" 201

TOKEN=$(curl -s -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"smoke@test.com","password":"pass1234"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
  echo "FAIL Login failed -- aborting remaining tests"
  exit 1
fi

# Rooms
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/rooms" \
  -H "Authorization: Bearer $TOKEN")
check "GET /rooms" "$STATUS" 200

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
```

---

## Feedback File Format (Evaluator -> Generator)

Written to `docs/feedback.md` on evaluation failure:

```markdown
## Sprint N Evaluation Result -- FAIL

### Failed Items
1. **Type error** (basedpyright)
   - `apps/server/app/routers/auth.py:42` -- Argument of type "str | None" cannot be assigned to parameter of type "str"
   - Fix direction: `user.email` is `str | None`, add None check before use

2. **Test failure**
   - `tests/test_auth.py::test_register_duplicate_email` -- AssertionError: 422 != 409
   - Fix direction: Should return 409 Conflict on duplicate email

3. **Sprint scope violation**
   - `apps/server/app/routers/rooms.py` -- File created outside Sprint 2 scope
   - Fix direction: Delete this file, implement in Sprint 3

### Re-implementation Instructions
Fix the 3 items above, then re-run `turbo check` + `pytest` and confirm all pass before declaring complete.
```
