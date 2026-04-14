# Chatty Client -- Design Spec

> WeeChat color palette and information density, but **no box borders**.  
> Separators are expressed only through colored background bars and indentation.

---

## Layout (Actual Rendering Example)

```
 #general  #mud  #random                              <- RoomBar (dim bg or bold)
---------------------------------------------------- <- Separator (single - characters, dim)
12:34  alice       Hello
12:35  bob         Nice to meet you
12:36  ***         Player joined                      <- system (yellow)
12:37  >>>         You are in a hall.                 <- game_response (green)
12:38   >          look                               <- game_command (dim)
                                                      <- (no empty lines, flexGrow fills)
---------------------------------------------------- <- Separator
[player1] _                                           <- InputBar
---------------------------------------------------- <- Separator
#general  3 users  SSE:*  player1         Ctrl+R:next <- StatusBar
```

**Key principle**: No boxes. Separator is a single line of `"-".repeat(cols)`. Visual hierarchy is created through bold/dim/color instead of background colors.

---

## Color Palette

| Element | Color | Ink Expression |
|---------|-------|----------------|
| RoomBar active tab | bold white | `<Text bold>` |
| RoomBar inactive tab | dim | `<Text dimColor>` |
| Separator (`-----`) | dim | `<Text dimColor>` |
| Timestamp | dim | `<Text dimColor>` |
| Nickname | hash-based (7 colors) | See palette below |
| chat message | white | default |
| system (`***`) | yellow | `<Text color="yellow">` |
| game_response (`>>>`) | green | `<Text color="green">` |
| game_command (`>`) | gray + dim | `<Text dimColor>` |
| SSE connected `*` | green | `<Text color="green">` |
| SSE reconnecting `*` | yellow | `<Text color="yellow">` |
| SSE disconnected `*` | red | `<Text color="red">` |
| StatusBar text | dim | `<Text dimColor>` |
| StatusBar emphasis | white | `<Text>` |

### Nickname Color Palette (7-color cycle)

Based on WeeChat default nick colors. Selected by charCode sum % 7 index.

```typescript
const NICK_COLORS = [
  "cyan", "yellow", "green", "magenta",
  "blue", "red", "white",
] as const
```

---

## Per-Component Rendering Spec

### RoomBar (renamed from RoomTabs)

```
 #general  #mud  #random
```

- Tab separation: 2 spaces
- Active: `bold` + `#` prefix
- Inactive: `dimColor`
- No overall background (WeeChat bar_bg omitted)

### Separator

```
----------------------------------------
```

- `"-".repeat(process.stdout.columns)` single line
- `dimColor`
- Extracted as a reusable `<Separator />` component

### MessageList

```
12:34  alice       Hello
```

**Column alignment**:
- Timestamp: fixed 5 chars (`HH:mm`), right padding 2 spaces
- Nickname: left-aligned, max 12 chars (`padEnd(12)`)  
  - system -> `***` (yellow)  
  - game_response -> `>>>` (green)  
  - game_command -> ` > ` (dim)  
- Message body: remaining width

**Per msg_type full-line treatment**:
- `chat`: timestamp dim, nickname nick-color, body white
- `system`: entire line yellow, nickname column `***`
- `game_response`: entire line green, nickname column `>>>`
- `game_command`: entire line dim, nickname column ` > `

### InputBar

```
[player1] _         (chat mode)
> _                 (game mode)
```

- Uses `ink-text-input`
- Prompt is dim, input text is white
- chat: `[nickname] `
- game: `> `
- Positioned between separators (Separator -> InputBar -> Separator)

### StatusBar

```
#general  3 users  * connected  player1            Ctrl+R:next
```

- 1 line, left side: room name (white bold) + user count (dim) + SSE status (* + color)
- Right side: nickname (dim) + key hints (dim)
- Left/right split: `<Box justifyContent="space-between">`
- No background color (WeeChat bar_bg omitted)

---

## Overall App Structure (app.tsx layout)

```tsx
<Box flexDirection="column" height={process.stdout.rows}>
  <RoomBar rooms={rooms} activeRoomId={activeRoomId} />
  <Separator />
  <Box flexGrow={1} overflow="hidden">
    <MessageList messages={visibleMessages} />
  </Box>
  <Separator />
  <InputBar ... />
  <Separator />
  <StatusBar ... />
</Box>
```

Total fixed rows: `1(RoomBar) + 1(Sep) + 1(Sep) + 1(InputBar) + 1(Sep) + 1(StatusBar) = 6`  
MessageList: uses `rows - 6` rows

---

## Scroll Behavior

- New message arrives + `isLocked = false` -> always show last line (auto-scroll)
- `PageUp` -> `isLocked = true`, scroll up
- `End` / manually after new message -> `isLocked = false`
- While scrolling, StatusBar shows `[scrolling -- End: jump to bottom]` hint

---

## Responsive Layout (Terminal Resize)

### Size Detection in Ink

```typescript
// Subscribe to cols/rows via Ink useStdout() -- auto-rerender on resize
const { stdout } = useStdout()
const cols = stdout.columns
const rows = stdout.rows
```

Either use `process.stdout.on('resize', ...)` + `useState` for forceUpdate,  
or use `useStdout()` directly and Ink will automatically re-render.

---

### Width (cols) Breakpoints

| cols Range | Behavior |
|------------|----------|
| < 40 | Show `Terminal too narrow (minimum 40 columns)` warning only, skip remaining render |
| 40-59 | Hide StatusBar right side (key hints). RoomBar shows active tab only. |
| 60-79 | Hide StatusBar key hints. Show full RoomBar. |
| >= 80 | Full layout |

### Height (rows) Breakpoints

| rows Range | Behavior |
|------------|----------|
| < 8 | Show `Terminal too short (minimum 8 rows)` warning only |
| >= 8 | Normal layout. `visibleRows = Math.max(1, rows - 6)` |

---

### Per-Component Resize Rules

**Separator**
- `"-".repeat(cols)` -- reads cols from `useStdout()`, so auto-reflects on resize

**RoomBar** -- when tabs exceed cols
```
cols >= 80:  #general  #mud  #random  #lobby  (all)
cols 60-79:  #general  #mud  ...+2    (active tab + earlier tabs, overflow shows ...+N)
cols 40-59:  #general  ...            (active tab only + ...)
```
- Active tab is always guaranteed to be visible

**MessageList**
- Message body width = `cols - 5(timestamp) - 2(pad) - 12(nick) - 2(pad)` = `cols - 21`
- If body exceeds this width, auto-wrap via Ink's `<Text wrap="wrap">`
- visibleRows is calculated based on actual rendered lines (a long message may occupy 2 rows)

**StatusBar** -- items shown per cols
```
cols >= 80:  #general  3 users  * connected  player1       Ctrl+R:next
cols 60-79:  #general  3 users  * connected  player1
cols 40-59:  #general  *
```

**InputBar**
- Input width = `cols - prompt.length` -- pass `columns` prop to `ink-text-input`
- If too narrow for even the prompt, shorten it: `[p1] ` -> `> `

---

### Resize Event Handling (app.tsx)

```typescript
const { stdout } = useStdout()
const [dims, setDims] = useState({ cols: stdout.columns, rows: stdout.rows })

useEffect(() => {
  const handler = () => setDims({ cols: stdout.columns, rows: stdout.rows })
  stdout.on("resize", handler)
  return () => { stdout.off("resize", handler) }
}, [stdout])
```

`dims` is passed down as props to RoomBar / Separator / MessageList / StatusBar / InputBar.

---

## Default Keybindings

| Key | Action |
|-----|--------|
| `Ctrl+R` | Next room |
| `Ctrl+Shift+R` | Previous room |
| `PageUp` | Scroll up |
| `PageDown` | Scroll down |
| `End` | Jump to bottom (unlock scroll) |
| `Up` / `Down` | Command history (game mode) |
| `Ctrl+C` | Exit |

---

## Differences from plan-client.md Summary

| Item | plan-client.md | This Design |
|------|----------------|-------------|
| Layout separators | Box borders (`+--+`) | Separator lines (`-----`) |
| RoomTabs | Inside box | Independent bar, no background |
| StatusBar | Inside box | Independent bar, no background |
| Nickname column | Unformatted | 12-char padded alignment |
| SSE status | Text (`SSE:connecting`) | `*` colored dot |
| GamePrompt | Separate component | Integrated as mode branch in InputBar |
| Separator component | None | Reusable `<Separator />` |
