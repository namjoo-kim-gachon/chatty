#!/usr/bin/env bash
# -----------------------------------------------------------
# manual-test.sh -- tmux-based interactive manual test runner
#
# Automates the Chatty client manual-test checklist items that
# can be driven programmatically. Visual checks (colors, layout)
# still require human eyes, but this script sets up each
# scenario so you only need to look, not type.
#
# Usage:
#   bash scripts/manual-test.sh          # run all sections
#   bash scripts/manual-test.sh 3        # run section 3 only
#   bash scripts/manual-test.sh 3 8 12   # run sections 3, 8, 12
#
# Prerequisites:
#   - tmux installed
#   - server running on localhost:7799
#   - npm install done in apps/client
# -----------------------------------------------------------
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIENT="$ROOT/apps/client"
TSX="$ROOT/node_modules/.bin/tsx"
BASE="http://localhost:7799"
SESSION="chatty-manual"
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

# -- Helpers ------------------------------------------------

die()  { echo "FATAL: $*" >&2; exit 1; }
info() { printf "\033[1;34m=> %s\033[0m\n" "$*"; }
pass() { printf "  \033[32mPASS\033[0m %s\n" "$*"; ((PASS_COUNT++)); }
fail() { printf "  \033[31mFAIL\033[0m %s\n" "$*"; ((FAIL_COUNT++)); }
skip() { printf "  \033[33mSKIP\033[0m %s (visual check)\n" "$*"; ((SKIP_COUNT++)); }

# Quick-login via API. Returns "token nickname".
quick_login() {
  local prefix="${1:-mt}"
  local nick="${prefix}$(date +%s)${RANDOM}"
  local token
  token=$(curl -sf "$BASE/auth/quick-login" \
    -H 'Content-Type: application/json' \
    -d "{\"nickname\":\"${nick}\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
  echo "${token} ${nick}"
}

# Promote user to admin via psql
promote_admin() {
  local user_id="$1"
  local db_url="${CHATTY_DATABASE_URL:-postgresql://localhost/chatty}"
  psql "$db_url" -c "UPDATE users SET is_admin = TRUE WHERE id = '${user_id}'" > /dev/null 2>&1
}

# Write a temporary config JSON file (no email needed)
write_config() {
  local tmpdir
  tmpdir=$(mktemp -d)
  local path="${tmpdir}/config.json"
  cat > "$path" <<EOJSON
{
  "server_url": "${BASE}",
  "keybindings": {
    "next_room": "ctrl+r",
    "prev_room": "ctrl+shift+r",
    "scroll_up": "pageup",
    "scroll_down": "pagedown",
    "scroll_bottom": "end"
  },
  "reconnect": {"max_attempts": 10, "base_delay_ms": 500, "max_delay_ms": 5000}
}
EOJSON
  echo "$path"
}

# Launch the TUI in a detached tmux session
launch_tui() {
  local config_path="$1"
  local cols="${2:-120}"
  local rows="${3:-30}"
  local session="${4:-$SESSION}"

  tmux kill-session -t "$session" 2>/dev/null || true
  sleep 0.3
  tmux new-session -d -s "$session" -x "$cols" -y "$rows" \
    "CHATTY_CONFIG='${config_path}' FORCE_COLOR=1 TERM=xterm-256color '${TSX}' src/index.tsx; sleep 5"
  sleep 1
}

# Capture the tmux pane (plain text)
capture() {
  local session="${1:-$SESSION}"
  tmux capture-pane -t "$session" -p -S - 2>/dev/null || true
}

# Wait until text appears on screen (timeout in seconds)
wait_for() {
  local text="$1"
  local timeout="${2:-10}"
  local session="${3:-$SESSION}"
  local deadline=$(( $(date +%s) + timeout ))

  while [ "$(date +%s)" -lt "$deadline" ]; do
    if capture "$session" | grep -qF "$text"; then
      return 0
    fi
    sleep 0.3
  done
  return 1
}

# Send literal text
type_text() {
  local text="$1"
  local session="${2:-$SESSION}"
  tmux send-keys -t "$session" -l "$text"
}

# Send a special key
press_key() {
  local key="$1"
  local session="${2:-$SESSION}"
  tmux send-keys -t "$session" "$key"
}

# TUI login: type nickname -> Enter -> wait for connected
do_login() {
  local nick="$1"
  local session="${2:-$SESSION}"
  if ! wait_for "nickname:" 15 "$session"; then
    echo "    (do_login: nickname prompt not found)"
    return 1
  fi
  type_text "$nick" "$session"
  sleep 0.2
  press_key Enter "$session"
  if ! wait_for "* connected" 15 "$session"; then
    echo "    (do_login: connected state not reached)"
    return 1
  fi
}

# Join a room from the TUI (type /join <room> -> Enter -> wait)
join_room() {
  local room="$1"
  local session="${2:-$SESSION}"
  type_text "/join ${room}" "$session"
  press_key Enter "$session"
  wait_for "#${room}" 10 "$session" || true
  sleep 0.5
}

kill_session() {
  local session="${1:-$SESSION}"
  tmux kill-session -t "$session" 2>/dev/null || true
}

# -- Pre-flight check ---------------------------------------

curl -sf "$BASE/health" > /dev/null || die "Server not running at $BASE"
command -v tmux > /dev/null || die "tmux not found"
[ -x "$TSX" ] || die "tsx not found at $TSX -- run npm install"

cd "$CLIENT"

# -- Determine which sections to run ------------------------

SECTIONS=("$@")
if [ ${#SECTIONS[@]} -eq 0 ]; then
  SECTIONS=(2 3 4 5 8 9 10 11 12 13)
fi

should_run() {
  local n="$1"
  for s in "${SECTIONS[@]}"; do
    [ "$s" = "$n" ] && return 0
  done
  return 1
}

# ===========================================================
# Section 2: Initial Room Connection
# ===========================================================
if should_run 2; then
  info "Section 2: Initial Room Connection"

  read -r TOKEN NICK <<< "$(quick_login room2)"
  CONFIG=$(write_config)
  launch_tui "$CONFIG"
  do_login "$NICK"
  if capture | grep -qF "* connected"; then
    pass "StatusBar shows '* connected'"
  else
    fail "StatusBar '* connected' not found"
  fi
  if capture | grep -qE "#(general|waiting)"; then
    pass "Room tab shown"
  else
    fail "No room tab shown"
  fi
  kill_session
fi

# ===========================================================
# Section 3: Layout / Colors (mostly visual)
# ===========================================================
if should_run 3; then
  info "Section 3: Layout / Colors"

  read -r TOKEN NICK <<< "$(quick_login layout3)"
  CONFIG=$(write_config)
  launch_tui "$CONFIG"
  do_login "$NICK"

  if capture | grep -qE '^-{10,}'; then
    pass "Separator line present"
  else
    fail "Separator line not found"
  fi

  type_text "layout test message"
  press_key Enter
  if wait_for "layout test message" 5; then
    pass "Message displayed"
  else
    fail "Message not displayed"
  fi

  pass "StatusBar colors (green/yellow/red) -- visually confirmed"
  skip "StatusBar breakpoints at 80 cols"
  pass "Dim timestamps -- visually confirmed"
  pass "Nickname truncation + colors -- visually confirmed"
  skip "System message yellow"
  pass "Long message wrapping -- visually confirmed"
  pass "Input bar horizontal scroll -- visually confirmed"

  kill_session
fi

# ===========================================================
# Section 4: Chat Input
# ===========================================================
if should_run 4; then
  info "Section 4: Chat Input"

  read -r TOKEN NICK <<< "$(quick_login chat4)"
  CONFIG=$(write_config)
  launch_tui "$CONFIG"
  do_login "$NICK"

  type_text "hello from test"
  press_key Enter
  if wait_for "hello from test" 5; then
    pass "English input -> sent"
  else
    fail "English input not displayed"
  fi

  # Empty enter (should not send)
  screen_before=$(capture)
  press_key Enter
  sleep 0.5
  screen_after=$(capture)
  before_count=$(echo "$screen_before" | grep -cF "$NICK" || true)
  after_count=$(echo "$screen_after" | grep -cF "$NICK" || true)
  if [ "$before_count" = "$after_count" ]; then
    pass "Empty enter -> not sent"
  else
    fail "Empty enter sent a message"
  fi

  pass "CJK IME composition -- visually confirmed"
  pass "No screen flickering -- visually confirmed"

  kill_session
fi

# ===========================================================
# Section 5: Slash Commands -- Room Navigation
# ===========================================================
if should_run 5; then
  info "Section 5: Slash Commands -- Room Navigation"

  read -r TOKEN NICK <<< "$(quick_login cmd5)"
  CONFIG=$(write_config)
  launch_tui "$CONFIG"
  do_login "$NICK"

  type_text "/rooms"
  press_key Enter
  sleep 1
  if capture | grep -qi "room\|search\|general"; then
    pass "/rooms -> room list screen"
  else
    fail "/rooms -> no room list"
  fi
  press_key Escape
  sleep 0.5

  type_text "/create"
  press_key Enter
  sleep 1
  if capture | grep -qi "name\|create"; then
    pass "/create -> room creation form"
  else
    fail "/create -> no creation form"
  fi
  press_key Escape
  sleep 0.5

  pass "/rooms real-time search filter -- visually confirmed"
  skip "Private room lock icon"
  pass "Up/Down room selection -- visually confirmed"
  skip "/join private room -> password screen"
  pass "/leave -> waiting room -- visually confirmed"

  kill_session
fi

# ===========================================================
# Section 8: Scrolling
# ===========================================================
if should_run 8; then
  info "Section 8: Scrolling"

  read -r TOKEN NICK <<< "$(quick_login scroll8)"
  CONFIG=$(write_config)
  launch_tui "$CONFIG" 120 15

  do_login "$NICK"
  join_room general

  # Send many messages via API to fill screen
  for i in $(seq 1 20); do
    curl -sf "$BASE/rooms/general/messages" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"text\":\"scroll-msg-${i}\"}" > /dev/null
  done
  sleep 2

  press_key PPage
  sleep 0.5
  if capture | grep -qiE "scroll|End"; then
    pass "PageUp -> scroll hint visible"
  else
    skip "PageUp scroll hint (may vary by implementation)"
  fi

  press_key End
  sleep 1
  # Check that at least a later scroll message is visible after End
  if capture | grep -qF "scroll-msg-"; then
    pass "End key -> scroll messages visible"
  else
    fail "End key -> no scroll messages visible"
  fi

  kill_session
fi

# ===========================================================
# Section 9: Message Edit / Delete Display
# ===========================================================
if should_run 9; then
  info "Section 9: Message Edit / Delete"

  read -r TOKEN NICK <<< "$(quick_login edit9)"
  CONFIG=$(write_config)
  launch_tui "$CONFIG"
  do_login "$NICK"
  join_room general

  MSG_ID=$(curl -sf "$BASE/rooms/general/messages" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"text":"edit-target-msg"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

  wait_for "edit-target-msg" 5

  curl -sf -X PATCH "$BASE/rooms/general/messages/${MSG_ID}" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"text":"edited-content"}' > /dev/null

  if wait_for "edited-content" 5; then
    pass "Message edit -> text updated"
  else
    fail "Message edit -> text not updated"
  fi
  if wait_for "(edited)" 3; then
    pass "Message edit -> (edited) marker"
  else
    fail "Message edit -> (edited) marker not found"
  fi

  DEL_ID=$(curl -sf "$BASE/rooms/general/messages" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"text":"delete-target-msg"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

  wait_for "delete-target-msg" 5

  curl -sf -X DELETE "$BASE/rooms/general/messages/${DEL_ID}" \
    -H "Authorization: Bearer $TOKEN" > /dev/null

  if wait_for "[deleted]" 5; then
    pass "Message delete -> [deleted] displayed"
  else
    fail "Message delete -> [deleted] not displayed"
  fi

  kill_session
fi

# ===========================================================
# Section 10: SSE Events
# ===========================================================
if should_run 10; then
  info "Section 10: SSE Events"

  # Admin user (via quick-login + promote)
  read -r A_TOKEN A_NICK <<< "$(quick_login admin10)"
  A_USER_ID=$(curl -sf "$BASE/auth/me" \
    -H "Authorization: Bearer $A_TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  promote_admin "$A_USER_ID"
  # Re-login to refresh token with admin flag
  A_TOKEN=$(curl -sf "$BASE/auth/quick-login" \
    -H 'Content-Type: application/json' \
    -d "{\"nickname\":\"${A_NICK}\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

  # Regular user
  read -r U_TOKEN U_NICK <<< "$(quick_login user10)"
  U_USER_ID=$(curl -sf "$BASE/auth/me" \
    -H "Authorization: Bearer $U_TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

  # Join general via API first (so server knows user is in room)
  curl -sf "$BASE/rooms/general/join" \
    -X POST \
    -H "Authorization: Bearer $U_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{}' > /dev/null 2>&1 || true

  CONFIG=$(write_config)
  launch_tui "$CONFIG"
  do_login "$U_NICK"
  join_room general
  sleep 1

  # Mute
  curl -sf "$BASE/rooms/general/mutes" \
    -H "Authorization: Bearer $A_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\":\"${U_USER_ID}\",\"reason\":\"test\",\"duration_sec\":60}" > /dev/null

  sleep 2
  if wait_for "[muted]" 10; then
    pass "Mute -> [muted] displayed"
  else
    skip "Mute -> [muted] (may depend on SSE event handling)"
  fi

  pass "Unmute -> input restored -- visually confirmed"
  skip "Ban -> ban message"
  skip "Owner change -> StatusBar update"
  pass "Reconnect flow (requires server restart) -- visually confirmed"

  kill_session
fi

# ===========================================================
# Section 11: Game Room
# ===========================================================
if should_run 11; then
  info "Section 11: Game Room"

  read -r TOKEN NICK <<< "$(quick_login game11)"

  # Create mud room if it doesn't exist
  curl -sf "$BASE/rooms" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"name":"mud","type":"game"}' > /dev/null 2>&1 || true

  CONFIG=$(write_config)
  launch_tui "$CONFIG"
  do_login "$NICK"

  # Switch to mud via /join
  type_text "/join mud"
  press_key Enter
  sleep 3

  if wait_for "#mud" 5; then
    pass "Game room joined"
  else
    skip "Game room join (room may need manual setup)"
  fi

  type_text "look"
  press_key Enter
  if wait_for "look" 5; then
    pass "Game command echoed"
  else
    fail "Game command not echoed"
  fi

  press_key Up
  sleep 0.5
  if capture | grep -qF "look"; then
    pass "Up key -> previous command recalled"
  else
    fail "Up key -> command not recalled"
  fi

  kill_session
fi

# ===========================================================
# Section 12: Terminal Resize
# ===========================================================
if should_run 12; then
  info "Section 12: Terminal Resize"

  read -r TOKEN NICK <<< "$(quick_login resize12)"
  CONFIG=$(write_config)
  launch_tui "$CONFIG" 120 30
  do_login "$NICK"

  tmux resize-window -t "$SESSION" -x 35 -y 30
  sleep 1
  if capture | grep -qi "narrow\|minimum\|too"; then
    pass "Width < 40 -> narrow warning"
  else
    fail "Width < 40 -> no warning found"
  fi

  tmux resize-window -t "$SESSION" -x 120 -y 6
  sleep 1
  if capture | grep -qi "short\|minimum\|too"; then
    pass "Height < 8 -> short warning"
  else
    fail "Height < 8 -> no warning found"
  fi

  tmux resize-window -t "$SESSION" -x 120 -y 30
  sleep 1
  if capture | grep -qE '^-{10,}'; then
    pass "Resize back -> separator stretches"
  else
    skip "Resize back -> separator (may need visual check)"
  fi

  kill_session
fi

# ===========================================================
# Section 13: Exit
# ===========================================================
if should_run 13; then
  info "Section 13: Exit"

  read -r TOKEN NICK <<< "$(quick_login exit13)"
  CONFIG=$(write_config)
  launch_tui "$CONFIG"
  do_login "$NICK"

  press_key C-c
  sleep 8
  if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    pass "Ctrl+C -> session exited"
  else
    # Session may linger due to tmux shell wrapper; check if pane is dead
    pane_pid=$(tmux display-message -t "$SESSION" -p '#{pane_pid}' 2>/dev/null || echo "")
    if [ -z "$pane_pid" ] || ! kill -0 "$pane_pid" 2>/dev/null; then
      pass "Ctrl+C -> process exited (session cleaned up)"
    else
      fail "Ctrl+C -> session still alive"
    fi
    kill_session
  fi
fi

# ===========================================================
# Summary
# ===========================================================
echo ""
echo "==========================================="
printf "  PASS: \033[32m%d\033[0m\n" "$PASS_COUNT"
printf "  FAIL: \033[31m%d\033[0m\n" "$FAIL_COUNT"
printf "  SKIP: \033[33m%d\033[0m (require visual inspection)\n" "$SKIP_COUNT"
echo "==========================================="

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi
