# Chatty Client -- Manual Test Checklist

Items that cannot be verified with automated e2e tests.  
Run `npm run dev` and follow the steps below in order.

---

## Environment Setup

```bash
# Start server (with --reload)
uv run uvicorn app.main:app --reload --port 7799 --app-dir apps/server

# Start client
cd apps/client && npm run dev
```

---

## 1. Login Screen

- [ ] Password input is masked with `*` and updates on a single line (no new lines added)
- [ ] Wrong password -> red error message, input reset
- [ ] Correct password -> `Connecting...` then main screen entry

---

## 2. Initial Room Connection

- [ ] If last connected room exists, auto-join that room
- [ ] If no last room or it was deleted -> enter `#waiting` waiting room
- [ ] StatusBar shows current room name, user count, `* connected`

---

## 3. Layout / Colors

- [ ] Separator: `-` characters fill the full terminal width
- [ ] StatusBar: `* connected` (green), `* reconnecting` (yellow), `* disconnected` (red)
- [ ] StatusBar: shows `[owner: nickname]` when width >= 80 columns
- [ ] Message timestamps: displayed dim
- [ ] Nickname column: truncated to max 12 chars, colored with one of 7 colors
- [ ] system messages (`***`): yellow
- [ ] game_response (`>>>`): green
- [ ] game_command (` > `): dim
- [ ] Long messages (including CJK characters) wrap correctly without breaking layout
- [ ] Long text in input bar stays on one line (scrolls left when overflowing)

---

## 4. Chat Input

- [ ] Korean (CJK) input: IME composition window appears at input cursor position
- [ ] Korean input followed by Enter -> message sent, input field cleared
- [ ] English input / Enter -> sent normally
- [ ] Empty message Enter -> not sent (ignored)
- [ ] No screen flickering while typing

---

## 5. Slash Commands -- Room Navigation

### `/rooms`

- [ ] Switches to room list screen
- [ ] Typing a search query filters in real-time
- [ ] Private rooms show lock icon
- [ ] `Up`/`Down` keys to select room, Enter to join
- [ ] Public room -> join immediately
- [ ] Private room -> switch to password input screen
- [ ] `Esc` -> return to chat screen (room preserved)

### `/create`

- [ ] Switches to room creation form screen
- [ ] `Tab`/`Shift+Tab` to navigate fields
- [ ] Name (required), description, password (masked), max members, slow mode input
- [ ] Enter (at last field or after name input) -> create room then auto-join
- [ ] `Esc` -> cancel and return to chat screen

### `/join <roomId>`

- [ ] Public room ID input -> join immediately
- [ ] Private room ID -> password input screen
- [ ] Non-existent room -> ignored (no error displayed)

### `/leave`

- [ ] From normal room: `/leave` -> move to waiting room (`#waiting`)
- [ ] From waiting room: `/leave` -> logout and exit

---

## 6. Slash Commands -- In-Room Features

### `/who`

- [ ] Switches to connected users list screen for current room
- [ ] Owner shown with star icon + yellow + `(owner)` label
- [ ] `Esc` -> return to chat screen

### `/me <action>`

- [ ] Sent as `action` type message (server-handled)
- [ ] Displayed in message list as `* nickname action` format

### `/topic <content>`

- [ ] Owner only -> updates announcement
- [ ] Non-owner -> error message
- [ ] SSE `room_updated` event propagates to other clients

### `/pass <nickname>`

- [ ] Owner only -> transfers ownership
- [ ] StatusBar `[owner: nickname]` updated
- [ ] Non-owner -> error message

---

## 7. Password Input Screen

- [ ] Password masked with `*`
- [ ] Correct password -> join room
- [ ] Wrong password -> error message displayed, can retry
- [ ] `Esc` -> cancel and return to previous screen

---

## 8. Scrolling

- [ ] When messages fill the screen, latest message is always visible at bottom (auto-scroll)
- [ ] `PageUp` -> scroll up, StatusBar shows `[scrolling -- End: bottom]` hint
- [ ] `PageDown` -> scroll down
- [ ] `End` key -> jump to bottom, hint disappears
- [ ] While scroll-locked, new messages arrive -> no auto-scroll (lock maintained)

---

## 9. Message Edit / Delete Display

(Verify after editing/deleting via another client or API)

- [ ] Message edit -> text changed + `(edited)` dim displayed at end of line
- [ ] Message delete -> `[deleted]` dim displayed

```bash
# For testing (replace token and msgId with actual values)
curl -X PATCH http://localhost:7799/rooms/{roomId}/messages/{msgId} \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"text": "edited content"}'
```

---

## 10. SSE Events

- [ ] On mute: `[muted] Input has been disabled.` displayed, input blocked
- [ ] On unmute: input field restored
- [ ] On ban/room deletion: `You are banned from this room. Use /leave to exit.` displayed in message area
- [ ] On owner change: StatusBar `[owner: nickname]` updates immediately
- [ ] On server restart: `* reconnecting` -> auto-reconnect -> `* connected`
- [ ] After reconnection, missed messages are recovered

---

## 11. Game Room

Create or join a `type: "game"` room, then verify.

- [ ] Prompt shows `> ` (chat rooms show `[nickname] `)
- [ ] `Up` key -> recall previous command
- [ ] `Down` key -> forward through command history

---

## 12. Terminal Resize

- [ ] Layout immediately readjusts on terminal size change
- [ ] Separator stretches to match new width
- [ ] Width < 40 columns -> `Terminal too narrow (minimum 40 columns)` warning
- [ ] Height < 8 rows -> `Terminal too short (minimum 8 rows)` warning
- [ ] StatusBar breakpoints: verify item changes at 40 / 60 / 80 columns

---

## 13. Exit

- [ ] `Ctrl+C` from normal room -> logout API call then exit
- [ ] `Ctrl+C` from waiting room -> logout then exit
- [ ] `Ctrl+C` from login screen -> exit immediately
