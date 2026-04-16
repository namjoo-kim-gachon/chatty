import React, { useState, useEffect, useCallback, useRef, useMemo } from "react"
import { Box, Text, useStdout, useInput, useApp } from "ink"
import type { AuthState, Config, Room, Screen } from "./types.js"
import { appBridge } from "./bridge.js"
import type { AppState, AppActions } from "./bridge.js"
import { Separator } from "./components/Separator.js"
import { MessageList } from "./components/MessageList.js"
import { InputBar } from "./components/InputBar.js"
import { StatusBar } from "./components/StatusBar.js"
import { RoomListScreen } from "./components/RoomListScreen.js"
import { UserListScreen } from "./components/UserListScreen.js"
import { CreateRoomForm } from "./components/CreateRoomForm.js"
import { PasswordInputScreen } from "./components/PasswordInputScreen.js"
import { useChat } from "./hooks/useChat.js"
import { useScroll } from "./hooks/useScroll.js"
import {
  sendMessage,
  getRoom,
  muteUser,
  unmuteUser,
  banUser,
  unbanUser,
  fetchBannedUsers,
} from "./lib/client.js"
import { computeTotalLines } from "./lib/textLayout.js"
import { logout } from "./lib/auth.js"
import { ThemeProvider } from "./theme/context.js"
import { LocaleProvider, useLocale } from "./i18n/context.js"
import { loadTheme } from "./theme/loader.js"
import { loadLocale } from "./i18n/loader.js"
import { interpolate } from "./i18n/interpolate.js"

const LOBBY_ROOM_ID = "lobby"
const LOCAL_MESSAGE_PREFIX = "local-"
const FORBIDDEN_ERROR = "403: Forbidden"

const KEY_END = "\u001B[F"
const KEY_END_ALT = "\u001B[4~"
const KEY_END_SS3 = "\u001BOF"
const KEY_HOME = "\u001B[H"
const KEY_HOME_ALT = "\u001B[1~"
const KEY_HOME_SS3 = "\u001BOH"
const KEY_PAGE_UP_VT100 = "\u001B[5~"
const KEY_PAGE_UP_VT220 = "\u001B[V"
const KEY_PAGE_DOWN_VT100 = "\u001B[6~"
const KEY_PAGE_DOWN_VT220 = "\u001B[U"
const VISIBLE_ROWS_OVERHEAD = 4
const MIN_COLS = 40
const MIN_ROWS = 8
const MS_PER_SECOND = 1000
const MOUSE_ENABLE = "\u001B[?1000h\u001B[?1006h"
const MOUSE_DISABLE = "\u001B[?1000l\u001B[?1006l"
const MOUSE_WHEEL_UP = 64
const MOUSE_WHEEL_DOWN = 65
const MOUSE_SCROLL_LINES = 3

interface AppProps {
  readonly config: Config
  readonly authState: AuthState
  readonly initialRoom: Room
  readonly onLogout?: (() => void) | undefined
}

function resolveLocaleCommand(
  cmd: string,
  locale: ReturnType<typeof useLocale>,
): string {
  const aliases: Record<string, string> = {
    [locale.commands.rooms]: "/rooms",
    [locale.commands.create]: "/create",
    [locale.commands.join]: "/join",
    [locale.commands.who]: "/who",
    [locale.commands.leave]: "/leave",
    [locale.commands.quit]: "/quit",
    [locale.commands.mute]: "/mute",
    [locale.commands.unmute]: "/unmute",
    [locale.commands.ban]: "/ban",
    [locale.commands.unban]: "/unban",
  }
  return aliases[cmd] ?? cmd
}

function ChatApp({
  config,
  authState,
  initialRoom,
  onLogout,
}: AppProps): React.ReactElement {
  const { exit } = useApp()
  const { stdout } = useStdout()
  const [dims, setDims] = useState({ cols: stdout.columns, rows: stdout.rows })
  const [screen, setScreen] = useState<Screen>({ type: "chat" })
  const [passwordError, setPasswordError] = useState("")
  const [showHelp, setShowHelp] = useState(false)
  const locale = useLocale()

  useEffect(() => {
    const handler = () => {
      setDims({ cols: stdout.columns, rows: stdout.rows })
    }
    stdout.on("resize", handler)
    return () => {
      stdout.off("resize", handler)
    }
  }, [stdout])

  const {
    activeRoom,
    messages,
    userCount,
    sseStatus,
    isMuted,
    isBanned,
    ownerNickname,
    nickColorMap,
    roomMembers,
    enterRoom,
    exitRoom,
    appendMessage,
    updateMuteStatus,
  } = useChat(config, authState, initialRoom)

  const visibleRows = Math.max(1, dims.rows - VISIBLE_ROWS_OVERHEAD)
  const totalLines = useMemo(
    () => computeTotalLines(messages, dims.cols),
    [messages, dims.cols],
  )
  const { scrollOffset, isScrollLocked, unlockScroll, scrollUp, scrollDown, scrollToTop } =
    useScroll(totalLines, visibleRows, stdout)

  useEffect(() => {
    stdout.write(MOUSE_ENABLE)
    return () => {
      stdout.write(MOUSE_DISABLE)
    }
  }, [stdout])

  useInput((input, key) => {
    // SGR mouse: Ink strips leading ESC, so \x1b[<btn;x;yM arrives as [<btn;x;yM
    const mouseSgr = /^\[<(\d+);\d+;\d+[Mm]$/.exec(input)
    if (mouseSgr !== null) {
      if (screen.type === "chat") {
        const button = Number(mouseSgr[1])
        if (button === MOUSE_WHEEL_UP) scrollUp(MOUSE_SCROLL_LINES)
        else if (button === MOUSE_WHEEL_DOWN) scrollDown(MOUSE_SCROLL_LINES)
      }
      return
    }
    if (screen.type !== "chat") return
    if (key.escape && showHelp) {
      setShowHelp(false)
      return
    }
    if (key.pageUp) {
      scrollUp(visibleRows)
      return
    }
    if (key.pageDown) {
      scrollDown(visibleRows)
      return
    }
    if (
      input === KEY_PAGE_UP_VT100 ||
      input === KEY_PAGE_UP_VT220
    ) {
      scrollUp(visibleRows)
      return
    }
    if (
      input === KEY_PAGE_DOWN_VT100 ||
      input === KEY_PAGE_DOWN_VT220
    ) {
      scrollDown(visibleRows)
      return
    }
    if (input === KEY_END || input === KEY_END_ALT || input === KEY_END_SS3) {
      unlockScroll()
      return
    }
    if (input === KEY_HOME || input === KEY_HOME_ALT || input === KEY_HOME_SS3) {
      scrollToTop()
      return
    }
    if (key.ctrl && input === "c") {
      exit()
    }
  })


  // Auto-exit to lobby when banned
  useEffect(() => {
    if (
      isBanned &&
      activeRoom !== undefined &&
      activeRoom.id !== LOBBY_ROOM_ID
    ) {
      exitRoom()
        .then(() => getRoom(config.server_url, LOBBY_ROOM_ID, authState.token))
        .then((lobby) => enterRoom(lobby))
        .catch(() => {
          // ignore
        })
    }
  }, [
    isBanned,
    activeRoom,
    config.server_url,
    authState.token,
    exitRoom,
    enterRoom,
  ])

  const addLocalSystem = useCallback(
    (text: string) => {
      appendMessage({
        // eslint-disable-next-line sonarjs/pseudo-random -- not security-sensitive
        id: `${LOCAL_MESSAGE_PREFIX}${String(Date.now())}-${String(Math.random())}`,
        room_id: activeRoom?.id ?? "",
        nickname: "",
        text,
        msg_type: "system",
        seq: -1,
        created_at: Date.now() / MS_PER_SECOND,
      })
    },
    [appendMessage, activeRoom],
  )

  const handleMuteToggle = useCallback(
    (isMuting: boolean, nickname: string) => {
      const room = activeRoom
      if (room === undefined) return
      if (ownerNickname !== authState.nickname) {
        addLocalSystem(locale.app.muteNotOwner)
        return
      }
      if (nickname.length === 0) return
      const target = [...roomMembers.values()].find(
        (u) => u.nickname === nickname,
      )
      if (target === undefined) {
        addLocalSystem(
          interpolate(locale.app.muteUserNotFound, { nick: nickname }),
        )
        return
      }
      const successMessage = isMuting
        ? locale.app.muteSuccess
        : locale.app.unmuteSuccess
      const failMessage = isMuting
        ? locale.app.muteFailed
        : locale.app.unmuteFailed
      const action = isMuting
        ? muteUser(config.server_url, room.id, authState.token, target.id)
        : unmuteUser(config.server_url, room.id, authState.token, target.id)
      action
        .then(() => {
          updateMuteStatus(target.id, isMuting)
          addLocalSystem(interpolate(successMessage, { nick: nickname }))
        })
        .catch(() => {
          addLocalSystem(failMessage)
        })
    },
    [
      activeRoom,
      config.server_url,
      authState.token,
      authState.nickname,
      ownerNickname,
      roomMembers,
      updateMuteStatus,
      addLocalSystem,
      locale,
    ],
  )

  function resolveUnban(nickname: string, roomId: string): Promise<void> {
    return fetchBannedUsers(config.server_url, roomId, authState.token).then(
      (banned) => {
        const target = banned.find((b) => b.nickname === nickname)
        if (target === undefined) throw new Error("not_found")
        return unbanUser(
          config.server_url,
          roomId,
          authState.token,
          target.user_id,
        )
      },
    )
  }

  const handleBan = useCallback(
    (nickname: string) => {
      const room = activeRoom
      if (room === undefined) return
      if (ownerNickname !== authState.nickname) {
        addLocalSystem(locale.app.banNotOwner)
        return
      }
      if (nickname.length === 0) return
      const target = [...roomMembers.values()].find(
        (u) => u.nickname === nickname,
      )
      if (target === undefined) {
        addLocalSystem(
          interpolate(locale.app.banUserNotFound, { nick: nickname }),
        )
        return
      }
      banUser(config.server_url, room.id, authState.token, target.id)
        .then(() => {
          addLocalSystem(interpolate(locale.app.banSuccess, { nick: nickname }))
        })
        .catch(() => {
          addLocalSystem(locale.app.banFailed)
        })
    },
    [
      activeRoom,
      config.server_url,
      authState.token,
      authState.nickname,
      ownerNickname,
      roomMembers,
      addLocalSystem,
      locale,
    ],
  )

  const handleUnban = useCallback(
    (nickname: string) => {
      const room = activeRoom
      if (room === undefined) return
      if (ownerNickname !== authState.nickname) {
        addLocalSystem(locale.app.banNotOwner)
        return
      }
      if (nickname.length === 0) return
      resolveUnban(nickname, room.id)
        .then(() => {
          addLocalSystem(
            interpolate(locale.app.unbanSuccess, { nick: nickname }),
          )
        })
        .catch((error: unknown) => {
          if (error instanceof Error && error.message === "not_found") {
            addLocalSystem(
              interpolate(locale.app.banUserNotFound, { nick: nickname }),
            )
          } else {
            addLocalSystem(locale.app.unbanFailed)
          }
        })
    },
    [
      activeRoom,
      config.server_url,
      authState.token,
      authState.nickname,
      ownerNickname,
      addLocalSystem,
      locale,
    ],
  )

  const handleCommand = useCallback(
    (text: string): boolean => {
      const parts = text.trim().split(/\s+/)
      const rawCmd = parts[0]?.toLowerCase() ?? ""
      const argument = parts.slice(1).join(" ")

      if (rawCmd.startsWith("/") && !rawCmd.startsWith("//")) {
        const englishCommands = [
          "/rooms",
          "/create",
          "/who",
          "/leave",
          "/join",
          "/?",
          "/quit",
          "/mute",
          "/unmute",
          "/ban",
          "/unban",
        ]
        const localeAliases = Object.values(locale.commands)
        if (![...englishCommands, ...localeAliases].includes(rawCmd)) {
          addLocalSystem(
            interpolate(locale.app.unknownCommand, { cmd: rawCmd }),
          )
          return true
        }
      }

      const cmd = resolveLocaleCommand(rawCmd, locale)

      switch (cmd) {
        case "/?": {
          setShowHelp((previous) => !previous)
          return true
        }
        case "/quit": {
          logout(config.server_url, authState.token)
            .then(() => {
              onLogout?.()
            })
            .catch(() => {
              onLogout?.()
            })
            .finally(() => {
              exit()
            })
          return true
        }
        case "/rooms": {
          setScreen({ type: "room_list" })
          return true
        }
        case "/create": {
          setScreen({ type: "create_room" })
          return true
        }
        case "/who": {
          if (activeRoom === undefined) return true
          setScreen({ type: "user_list" })
          return true
        }
        case "/leave": {
          const room = activeRoom
          if (room === undefined) return true
          if (room.id === LOBBY_ROOM_ID) {
            exit()
            return true
          }
          exitRoom()
            .then(() =>
              getRoom(config.server_url, LOBBY_ROOM_ID, authState.token),
            )
            .then((lobby) => enterRoom(lobby))
            .catch(() => {
              // ignore
            })
          return true
        }
        case "/join": {
          if (argument.length === 0) return true
          getRoom(config.server_url, argument, authState.token)
            .then((room) => {
              if (room.is_private) {
                setPasswordError("")
                setScreen({
                  type: "password_input",
                  roomId: room.id,
                  roomName: room.name,
                })
              } else {
                enterRoom(room).catch((error: unknown) => {
                  const errorMessage =
                    error instanceof Error
                      ? error.message
                      : locale.app.joinFailed
                  addLocalSystem(
                    errorMessage === "Banned" ||
                      errorMessage === FORBIDDEN_ERROR
                      ? locale.app.banned
                      : errorMessage,
                  )
                })
              }
            })
            .catch(() => {
              // ignore
            })
          return true
        }
        case "/mute": {
          handleMuteToggle(true, argument)
          return true
        }
        case "/unmute": {
          handleMuteToggle(false, argument)
          return true
        }
        case "/ban": {
          handleBan(argument)
          return true
        }
        case "/unban": {
          handleUnban(argument)
          return true
        }
        default: {
          return false
        }
      }
    },
    [
      activeRoom,
      config.server_url,
      authState.token,
      exitRoom,
      enterRoom,
      exit,
      addLocalSystem,
      handleMuteToggle,
      handleBan,
      handleUnban,
      locale,
    ],
  )

  const handleSubmit = useCallback(
    (text: string) => {
      if (activeRoom === undefined) return
      if (handleCommand(text)) return
      if (!isScrollLocked) unlockScroll()
      if (isMuted) {
        appendMessage({
          // eslint-disable-next-line sonarjs/pseudo-random -- not security-sensitive
          id: `${LOCAL_MESSAGE_PREFIX}${String(Date.now())}-${String(Math.random())}`,
          room_id: activeRoom.id,
          nickname: authState.nickname,
          text,
          msg_type: "chat",
          seq: -1,
          created_at: Date.now() / MS_PER_SECOND,
        })
        return
      }
      sendMessage(
        config.server_url,
        activeRoom.id,
        authState.token,
        text,
      ).catch((error: unknown) => {
        if (error instanceof Error && error.message.startsWith("403")) {
          appendMessage({
            // eslint-disable-next-line sonarjs/pseudo-random -- not security-sensitive
            id: `${LOCAL_MESSAGE_PREFIX}${String(Date.now())}-${String(Math.random())}`,
            room_id: activeRoom.id,
            nickname: "",
            text: locale.app.adminOnly,
            msg_type: "system",
            seq: -1,
            created_at: Date.now() / MS_PER_SECOND,
          })
        }
      })
    },
    [
      activeRoom,
      isMuted,
      appendMessage,
      authState.nickname,
      authState.token,
      config.server_url,
      handleCommand,
      isScrollLocked,
      unlockScroll,
    ],
  )

  const handleSubmitRef = useRef(handleSubmit)
  handleSubmitRef.current = handleSubmit
  const stableHandleSubmit = useCallback((text: string) => {
    handleSubmitRef.current(text)
  }, [])

  const bridgeStateRef = useRef<() => AppState>(() => ({
    authState,
    config,
    activeRoom,
    messages,
    userCount,
    sseStatus,
    isMuted,
    isBanned,
    ownerNickname,
    screen: screen.type,
  }))
  bridgeStateRef.current = () => ({
    authState,
    config,
    activeRoom,
    messages,
    userCount,
    sseStatus,
    isMuted,
    isBanned,
    ownerNickname,
    screen: screen.type,
  })

  const bridgeActionsRef = useRef({
    enterRoom,
    exitRoom,
    sendMessage: (text: string) =>
      sendMessage(
        config.server_url,
        activeRoom?.id ?? "",
        authState.token,
        text,
      ),
  })
  bridgeActionsRef.current = {
    enterRoom,
    exitRoom,
    sendMessage: (text: string) =>
      sendMessage(
        config.server_url,
        activeRoom?.id ?? "",
        authState.token,
        text,
      ),
  }

  useEffect(() => {
    appBridge.registerState(() => bridgeStateRef.current())
    appBridge.registerActions({
      enterRoom: (...args) => bridgeActionsRef.current.enterRoom(...args),
      exitRoom: () => bridgeActionsRef.current.exitRoom(),
      sendMessage: (text) => bridgeActionsRef.current.sendMessage(text),
    })
  }, [])

  const handleMuteFromList = useCallback(
    (userId: string, isMuted: boolean) => {
      const room = activeRoom
      if (room === undefined) return
      const action = isMuted
        ? unmuteUser(config.server_url, room.id, authState.token, userId)
        : muteUser(config.server_url, room.id, authState.token, userId)
      action
        .then(() => {
          updateMuteStatus(userId, !isMuted)
        })
        .catch(() => {
          // ignore
        })
    },
    [activeRoom, config.server_url, authState.token, updateMuteStatus],
  )

  const handleBanFromList = useCallback(
    (userId: string) => {
      const room = activeRoom
      if (room === undefined) return
      banUser(config.server_url, room.id, authState.token, userId).catch(() => {
        // ignore
      })
    },
    [activeRoom, config.server_url, authState.token],
  )

  if (dims.cols < MIN_COLS) {
    return (
      <Box>
        <Text color="red">{locale.app.tooNarrow}</Text>
      </Box>
    )
  }
  if (dims.rows < MIN_ROWS) {
    return (
      <Box>
        <Text color="red">{locale.app.tooShort}</Text>
      </Box>
    )
  }

  if (screen.type === "room_list") {
    return (
      <Box flexDirection="column" height={dims.rows}>
        <RoomListScreen
          config={config}
          authState={authState}
          onSelect={(room) => {
            if (room.is_private) {
              setPasswordError("")
              setScreen({
                type: "password_input",
                roomId: room.id,
                roomName: room.name,
              })
            } else {
              setScreen({ type: "chat" })
              enterRoom(room).catch((error: unknown) => {
                const errorMessage =
                  error instanceof Error ? error.message : locale.app.joinFailed
                addLocalSystem(
                  errorMessage === "Banned" || errorMessage === FORBIDDEN_ERROR
                    ? locale.app.banned
                    : errorMessage,
                )
              })
            }
          }}
          onCancel={() => {
            setScreen({ type: "chat" })
          }}
          cols={dims.cols}
          rows={dims.rows}
        />
      </Box>
    )
  }

  if (screen.type === "user_list") {
    return (
      <Box flexDirection="column" height={dims.rows}>
        <UserListScreen
          roomName={activeRoom?.name ?? ""}
          users={[...roomMembers.values()]}
          ownerNickname={ownerNickname}
          myNickname={authState.nickname}
          onClose={() => {
            setScreen({ type: "chat" })
          }}
          onMuteToggle={handleMuteFromList}
          onBanUser={handleBanFromList}
          cols={dims.cols}
          rows={dims.rows}
        />
      </Box>
    )
  }

  if (screen.type === "create_room") {
    return (
      <Box flexDirection="column" height={dims.rows}>
        <CreateRoomForm
          config={config}
          authState={authState}
          onCreated={(room) => {
            setScreen({ type: "chat" })
            enterRoom(room).catch((error: unknown) => {
              const errorMessage =
                error instanceof Error ? error.message : locale.app.joinFailed
              addLocalSystem(
                errorMessage === "Banned" || errorMessage === FORBIDDEN_ERROR
                  ? locale.app.banned
                  : errorMessage,
              )
            })
          }}
          onCancel={() => {
            setScreen({ type: "chat" })
          }}
        />
      </Box>
    )
  }

  if (screen.type === "password_input") {
    const { roomId, roomName } = screen
    return (
      <Box flexDirection="column" height={dims.rows}>
        <PasswordInputScreen
          roomName={roomName}
          error={passwordError}
          onSubmit={(password) => {
            getRoom(config.server_url, roomId, authState.token)
              .then((room) =>
                enterRoom(room, password)
                  .then(() => {
                    setPasswordError("")
                    setScreen({ type: "chat" })
                  })
                  .catch((error: unknown) => {
                    const errorMessage =
                      error instanceof Error
                        ? error.message
                        : locale.app.wrongPassword
                    setPasswordError(
                      errorMessage === "Banned" ||
                        errorMessage === FORBIDDEN_ERROR
                        ? locale.app.banned
                        : errorMessage,
                    )
                  }),
              )
              .catch(() => {
                setPasswordError(locale.app.roomLoadFailed)
              })
          }}
          onCancel={() => {
            setPasswordError("")
            setScreen({ type: "chat" })
          }}
        />
      </Box>
    )
  }

  const fallbackRoom: Room = {
    id: "",
    room_number: 0,
    name: "...",
    type: "chat",
    description: "",
    is_private: false,
    max_members: 500,
    slow_mode_sec: 1,
    owner_nickname: "",
    user_count: 0,
  }

  return (
    <Box flexDirection="column">
      <Box height={visibleRows} overflow="hidden">
        {isBanned ? (
          <Box paddingX={1}>
            <Text color="red">{locale.app.banned}</Text>
          </Box>
        ) : (
          <MessageList
            messages={messages}
            visibleRows={visibleRows}
            scrollOffset={scrollOffset}
            cols={dims.cols}
            myNickname={authState.nickname}
            nickColorMap={nickColorMap}
          />
        )}
      </Box>
      <Separator />
      <InputBar
        roomType={activeRoom?.type ?? "chat"}
        nickname={authState.nickname}
        onSubmit={stableHandleSubmit}
        cols={dims.cols}
      />
      <Separator />
      <StatusBar
        room={activeRoom ?? fallbackRoom}
        userCount={userCount}
        sseStatus={sseStatus}
        isScrollLocked={isScrollLocked}
        ownerNickname={ownerNickname}
        cols={dims.cols}
        showHelp={showHelp}
      />
    </Box>
  )
}

interface AppInnerProps {
  readonly config: Config
  readonly authState: AuthState
  readonly onLogout?: (() => void) | undefined
}

function AppInner({
  config,
  authState,
  onLogout,
}: AppInnerProps): React.ReactElement {
  const locale = useLocale()
  const [initialRoom, setInitialRoom] = useState<Room | undefined>()
  const [loadError, setLoadError] = useState("")

  useEffect(() => {
    getRoom(config.server_url, LOBBY_ROOM_ID, authState.token)
      .then((room) => {
        setInitialRoom(room)
      })
      .catch(() => {
        setLoadError(locale.app.loadFailed)
      })
  }, [config.server_url, authState.token, locale.app.loadFailed])

  if (loadError.length > 0) {
    return (
      <Box>
        <Text color="red">{loadError}</Text>
      </Box>
    )
  }
  if (initialRoom === undefined) {
    return (
      <Box>
        <Text dimColor>{locale.app.connecting}</Text>
      </Box>
    )
  }

  return (
    <ChatApp
      config={config}
      authState={authState}
      initialRoom={initialRoom}
      onLogout={onLogout}
    />
  )
}

interface AppLoaderProps {
  readonly config: Config
  readonly authState: AuthState
  readonly onLogout?: (() => void) | undefined
}

export function App({
  config,
  authState,
  onLogout,
}: AppLoaderProps): React.ReactElement {
  const theme = useMemo(() => loadTheme(config.theme), [config.theme])
  const locale = useMemo(() => loadLocale(config.locale), [config.locale])

  return (
    <ThemeProvider theme={theme}>
      <LocaleProvider locale={locale}>
        <AppInner config={config} authState={authState} onLogout={onLogout} />
      </LocaleProvider>
    </ThemeProvider>
  )
}
