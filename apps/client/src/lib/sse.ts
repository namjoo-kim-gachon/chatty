import EventSource from "eventsource"
import type { GameState, Message, Room, SSEStatus } from "../types.js"
import { sanitizeMessage } from "./client.js"

export type SSEEvent =
  | { event: "init"; data: { is_muted: boolean } }
  | { event: "message"; data: Message }
  | {
      event: "user_joined"
      data: { user_id: string; nickname: string; is_muted: boolean }
    }
  | { event: "user_left"; data: { user_id: string } }
  | { event: "system"; data: { text: string } }
  | { event: "room_updated"; data: Partial<Room> }
  | { event: "kicked"; data: { reason: string } }
  | { event: "banned"; data: { reason: string; expires_at: number | null } }
  | { event: "muted"; data: { reason: string; expires_at: number | null } }
  | { event: "unmuted"; data: Record<string, never> }
  | { event: "owner_changed"; data: { new_owner: string } }
  | { event: "room_deleted"; data: { room_id: string } }
  | { event: "game_state"; data: GameState }

export type SSEStatusHandler = (status: SSEStatus, attempt?: number) => void

const JITTER_MIN = 0.85
const JITTER_RANGE = 0.3
const DEFAULT_MAX_ATTEMPTS = 10
const DEFAULT_BASE_DELAY_MS = 1000
const DEFAULT_MAX_DELAY_MS = 30_000

export function backoffDelay(
  attempt: number,
  base: number,
  max: number,
): number {
  // Using Math.random() for jitter is safe here -- this is not security-sensitive
  // eslint-disable-next-line sonarjs/pseudo-random
  const jitter = JITTER_MIN + Math.random() * JITTER_RANGE
  return Math.min(base * Math.pow(2, attempt) * jitter, max)
}

const SSE_EVENTS = [
  "init",
  "message",
  "user_joined",
  "user_left",
  "system",
  "room_updated",
  "kicked",
  "banned",
  "muted",
  "unmuted",
  "owner_changed",
  "room_deleted",
  "game_state",
] as const

type SSEEventName = (typeof SSE_EVENTS)[number]

function isSseEventName(name: string): name is SSEEventName {
  return (SSE_EVENTS as readonly string[]).includes(name)
}

export function createSSEConnection(
  serverUrl: string,
  roomId: string,
  token: string,
  onEvent: (event: SSEEvent) => void,
  onStatus: SSEStatusHandler,
  options?: {
    maxAttempts?: number
    baseDelay?: number
    maxDelay?: number
  },
): { close(): void } {
  const maxAttempts = options?.maxAttempts ?? DEFAULT_MAX_ATTEMPTS
  const baseDelay = options?.baseDelay ?? DEFAULT_BASE_DELAY_MS
  const maxDelay = options?.maxDelay ?? DEFAULT_MAX_DELAY_MS

  let es: InstanceType<typeof EventSource> | null = null
  let attempt = 0
  let closed = false
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function connect(): void {
    if (closed) return

    const url = `${serverUrl}/rooms/${roomId}/stream`
    es = new EventSource(url, { headers: { Authorization: `Bearer ${token}` } })

    es.addEventListener("open", () => {
      attempt = 0
      onStatus("connected")
    })

    for (const eventName of SSE_EVENTS) {
      es.addEventListener(eventName, (raw: MessageEvent) => {
        if (closed) return
        try {
          const parsed = JSON.parse(raw.data as string) as unknown
          if (!isSseEventName(eventName)) return
          if (eventName === "message") {
            const message = sanitizeMessage(
              parsed as Parameters<typeof sanitizeMessage>[0],
            )
            onEvent({ event: "message", data: message })
          } else {
            onEvent({ event: eventName, data: parsed } as SSEEvent)
          }
        } catch {
          // ignore parse errors
        }
      })
    }

    es.addEventListener("error", () => {
      if (closed) return
      es?.close()
      es = null
      scheduleReconnect()
    })
  }

  function scheduleReconnect(): void {
    if (closed) return
    if (attempt >= maxAttempts) {
      // Switch to slow-poll mode: keep retrying at maxDelay interval
      onStatus("disconnected", attempt)
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null
        if (!closed) {
          connect()
        }
      }, maxDelay)
      return
    }
    attempt++
    onStatus("reconnecting", attempt)
    const delay = backoffDelay(attempt, baseDelay, maxDelay)
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, delay)
  }

  connect()

  return {
    close() {
      closed = true
      if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      es?.close()
      es = null
    },
  }
}
