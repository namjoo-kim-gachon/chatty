import { useState, useEffect, useCallback, useRef } from "react"
import type {
  GameState,
  Room,
  Message,
  SSEStatus,
  Config,
  AuthState,
  UserEntry,
} from "../types.js"
import {
  fetchMessages,
  fetchUsersWithIds,
  fetchMutedUserIds,
  joinRoom,
  leaveRoom,
} from "../lib/client.js"
import { createSSEConnection } from "../lib/sse.js"
import type { SSEEvent } from "../lib/sse.js"
import { useLocale } from "../i18n/context.js"
import { interpolate } from "../i18n/interpolate.js"

const MS_PER_SECOND = 1000

const LOBBY_ROOM_ID = "lobby"
const KICK_RECONNECT_DELAY_MS = 1000
const MAX_NICK_SLOTS = 100

interface UseChatResult {
  activeRoom: Room | undefined
  messages: Message[]
  userCount: number
  sseStatus: SSEStatus
  isMuted: boolean
  isBanned: boolean
  ownerNickname: string
  gameState: GameState | undefined
  nickColorMap: ReadonlyMap<string, number>
  roomMembers: ReadonlyMap<string, UserEntry>
  enterRoom: (room: Room, password?: string) => Promise<void>
  exitRoom: () => Promise<void>
  appendMessage: (message: Message) => void
  setOwnerNickname: (nickname: string) => void
  updateMuteStatus: (userId: string, isMuted: boolean) => void
}

function mergeMessages(existing: Message[], incoming: Message[]): Message[] {
  const seen = new Set(existing.map((message) => message.id))
  const merged = [...existing]
  for (const message of incoming) {
    if (!seen.has(message.id)) {
      seen.add(message.id)
      merged.push(message)
    }
  }
  merged.sort((a, b) => a.seq - b.seq)
  return merged
}

function appendUnique(previous: Message[], message: Message): Message[] {
  if (previous.some((m) => m.id === message.id)) return previous
  return [...previous, message]
}

function handleDisconnect(
  setIsBanned: (v: boolean) => void,
  closeSse: () => void,
  setSseStatus: (v: SSEStatus) => void,
): void {
  setIsBanned(true)
  closeSse()
  setSseStatus("disconnected")
}

export function useChat(
  config: Config,
  authState: AuthState,
  initialRoom: Room | undefined,
): UseChatResult {
  const locale = useLocale()
  const localeRef = useRef(locale)
  localeRef.current = locale

  const [activeRoom, setActiveRoom] = useState(initialRoom)
  const [messages, setMessages] = useState<Message[]>([])
  const [userCount, setUserCount] = useState(0)
  const [sseStatus, setSseStatus] = useState<SSEStatus>("disconnected")
  const [isMuted, setIsMuted] = useState(false)
  const [isBanned, setIsBanned] = useState(false)
  const [ownerNickname, setOwnerNickname] = useState(
    initialRoom?.owner_nickname ?? "",
  )
  const [gameState, setGameState] = useState<GameState | undefined>()
  const [nickColorMap, setNickColorMap] = useState(
    new Map(),
  )
  const [roomMembers, setRoomMembers] = useState(
    new Map(),
  )

  const lastSeqRef = useRef(0)
  const sseCloseRef = useRef<(() => void) | undefined>(undefined)
  const activeRoomRef = useRef(initialRoom)
  const nickSlotsRef = useRef(new Map())
  const usedSlotsRef = useRef(new Set())
  // Ref mirror of roomMembers for use inside SSE event closures
  const roomMembersRef = useRef(new Map())

  const closeSse = useCallback(() => {
    sseCloseRef.current?.()
    sseCloseRef.current = undefined
  }, [])

  const assignNickColor = useCallback((nickname: string) => {
    if (nickSlotsRef.current.has(nickname)) return
    for (let index = 0; index < MAX_NICK_SLOTS; index++) {
      if (!usedSlotsRef.current.has(index)) {
        usedSlotsRef.current.add(index)
        nickSlotsRef.current.set(nickname, index)
        setNickColorMap(new Map(nickSlotsRef.current))
        return
      }
    }
  }, [])

  const freeNickColor = useCallback((nickname: string) => {
    const slot = nickSlotsRef.current.get(nickname)
    if (slot !== undefined) {
      usedSlotsRef.current.delete(slot)
      nickSlotsRef.current.delete(nickname)
      setNickColorMap(new Map(nickSlotsRef.current))
    }
  }, [])

  const resetNickColors = useCallback(() => {
    nickSlotsRef.current.clear()
    usedSlotsRef.current.clear()
    setNickColorMap(new Map())
  }, [])

  const addSystemMessage = useCallback((text: string) => {
    setMessages((previous) =>
      appendUnique(previous, {
        // eslint-disable-next-line sonarjs/pseudo-random -- not security-sensitive
        id: `local-${String(Date.now())}-${String(Math.random())}`,
        room_id: activeRoomRef.current?.id ?? "",
        nickname: "",
        text,
        msg_type: "system",
        seq: -1,
        created_at: Date.now() / MS_PER_SECOND,
      }),
    )
  }, [])

  const updateMuteStatus = useCallback((userId: string, isMuted: boolean) => {
    const existing = roomMembersRef.current.get(userId)
    if (existing === undefined) return
    const updated = new Map(roomMembersRef.current)
    updated.set(userId, { ...existing, isMuted })
    roomMembersRef.current = updated
    setRoomMembers(updated)
  }, [])

  const refreshMembers = useCallback(
    (roomId: string) => {
      Promise.all([
        fetchUsersWithIds(config.server_url, roomId, authState.token),
        fetchMutedUserIds(config.server_url, roomId, authState.token),
      ])
        .then(([users, mutedIds]) => {
          const mutedSet = new Set(mutedIds)
          setUserCount(users.length)
          const newMap = new Map<string, UserEntry>()
          for (const user of users) {
            assignNickColor(user.nickname)
            newMap.set(user.id, {
              id: user.id,
              nickname: user.nickname,
              isMuted: mutedSet.has(user.id),
            })
          }
          roomMembersRef.current = newMap
          setRoomMembers(new Map(newMap))
        })
        .catch(() => {
          // ignore errors on refresh
        })
    },
    [config.server_url, authState.token, assignNickColor],
  )

  const recoverMissedMessages = useCallback(
    (roomId: string, sinceSeq: number) => {
      fetchMessages(config.server_url, roomId, authState.token, {
        since_seq: sinceSeq,
      })
        .then((missed) => {
          if (missed.length > 0) {
            setMessages((previous) => mergeMessages(previous, missed))
          }
        })
        .catch(() => {
          // ignore recovery errors
        })
    },
    [config.server_url, authState.token],
  )

  const connectSSE = useCallback(
    (room: Room) => {
      closeSse()

      const handleEvent = (event: SSEEvent) => {
        switch (event.event) {
          case "init": {
            setIsMuted(event.data.is_muted)
            break
          }
          case "message": {
            const incomingMessage = event.data
            setMessages((previous) => {
              const updated = appendUnique(previous, incomingMessage)
              lastSeqRef.current = Math.max(
                lastSeqRef.current,
                incomingMessage.seq,
              )
              return updated
            })
            break
          }
          case "user_joined": {
            const { user_id, nickname } = event.data
            setUserCount((previous) => previous + 1)
            assignNickColor(nickname)
            const joined: UserEntry = {
              id: user_id,
              nickname,
              isMuted: false,
            }
            const next = new Map(roomMembersRef.current)
            next.set(user_id, joined)
            roomMembersRef.current = next
            setRoomMembers(new Map(next))
            addSystemMessage(
              interpolate(localeRef.current.app.userJoined, {
                nick: nickname,
              }),
            )
            break
          }
          case "user_left": {
            const { user_id } = event.data
            setUserCount((previous) => Math.max(0, previous - 1))
            const leaving = roomMembersRef.current.get(user_id)
            if (leaving !== undefined) {
              freeNickColor(leaving.nickname)
              addSystemMessage(
                interpolate(localeRef.current.app.userLeft, {
                  nick: leaving.nickname,
                }),
              )
            }
            const next = new Map(roomMembersRef.current)
            next.delete(user_id)
            roomMembersRef.current = next
            setRoomMembers(new Map(next))
            break
          }
          case "owner_changed": {
            setOwnerNickname(event.data.new_owner)
            break
          }
          case "room_deleted": {
            handleDisconnect(setIsBanned, closeSse, setSseStatus)
            break
          }
          case "kicked": {
            closeSse()
            setSseStatus("reconnecting")
            const kickedRoom = room
            setTimeout(() => {
              if (activeRoomRef.current?.id === kickedRoom.id) {
                connectSSE(kickedRoom)
              }
            }, KICK_RECONNECT_DELAY_MS)
            break
          }
          case "banned": {
            handleDisconnect(setIsBanned, closeSse, setSseStatus)
            // Leave the room automatically when banned
            void leaveRoom(config.server_url, room.id, authState.token)
            break
          }
          case "muted": {
            setIsMuted(true)
            addSystemMessage(localeRef.current.app.muted)
            break
          }
          case "unmuted": {
            setIsMuted(false)
            addSystemMessage(localeRef.current.app.unmuted)
            break
          }
          case "game_state": {
            setGameState(event.data)
            break
          }
          default: {
            break
          }
        }
      }

      const handleStatus = (status: SSEStatus) => {
        setSseStatus(status)
        if (status === "connected") {
          const currentSeq = lastSeqRef.current
          if (currentSeq > 0) {
            recoverMissedMessages(room.id, currentSeq)
          }
          refreshMembers(room.id)
        }
      }

      const connection = createSSEConnection(
        config.server_url,
        room.id,
        authState.token,
        handleEvent,
        handleStatus,
        {
          maxAttempts: config.reconnect.max_attempts,
          baseDelay: config.reconnect.base_delay_ms,
          maxDelay: config.reconnect.max_delay_ms,
        },
      )
      sseCloseRef.current = () => {
        connection.close()
      }
    },
    [
      config,
      authState.token,
      recoverMissedMessages,
      refreshMembers,
      closeSse,
      assignNickColor,
      freeNickColor,
    ],
  )

  const enterRoom = useCallback(
    async (room: Room, password?: string) => {
      await joinRoom(config.server_url, room.id, authState.token, password)

      closeSse()
      activeRoomRef.current = room
      setActiveRoom(room)
      setMessages([])
      setIsMuted(false)
      setIsBanned(false)
      setOwnerNickname(room.owner_nickname)
      setGameState(undefined)
      resetNickColors()
      roomMembersRef.current = new Map()
      setRoomMembers(new Map())
      lastSeqRef.current = 0

      const msgs = await fetchMessages(
        config.server_url,
        room.id,
        authState.token,
        { limit: 50 },
      )
      setMessages(msgs)
      const last = msgs.at(-1)
      if (last !== undefined) lastSeqRef.current = last.seq

      connectSSE(room)
    },
    [config.server_url, authState.token, closeSse, connectSSE, resetNickColors],
  )

  const exitRoom = useCallback(async () => {
    if (activeRoom === undefined) return
    if (activeRoom.id === LOBBY_ROOM_ID) return
    await leaveRoom(config.server_url, activeRoom.id, authState.token)
  }, [activeRoom, config.server_url, authState.token])

  const appendMessage = useCallback((message: Message) => {
    setMessages((previous) => appendUnique(previous, message))
  }, [])

  // Connect SSE when initial room is set
  useEffect(() => {
    if (initialRoom === undefined) return
    activeRoomRef.current = initialRoom
    connectSSE(initialRoom)

    fetchMessages(config.server_url, initialRoom.id, authState.token, {
      limit: 50,
    })
      .then((msgs) => {
        setMessages(msgs)
        const last = msgs.at(-1)
        if (last !== undefined) lastSeqRef.current = last.seq
      })
      .catch(() => {
        // ignore
      })

    return () => {
      closeSse()
    }
    // intentionally run once on mount
  }, [])

  return {
    activeRoom,
    messages,
    userCount,
    sseStatus,
    isMuted,
    isBanned,
    ownerNickname,
    gameState,
    nickColorMap,
    roomMembers,
    enterRoom,
    exitRoom,
    appendMessage,
    setOwnerNickname,
    updateMuteStatus,
  }
}
