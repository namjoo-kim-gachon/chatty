import type { Room, Message, RoomType, MessageType } from "../types.js"

interface RoomSummaryResponse {
  id: string
  room_number: number
  name: string
  type: string
  description: string
  is_private: boolean
  max_members: number
  slow_mode_sec: number
  user_count: number
  owner_nickname: string
}

interface MessageResponse {
  id: string
  room_id: string
  nickname: string
  text: string
  msg_type: string
  seq: number
  created_at: number
}

interface SendMessageResponse {
  id?: string
  seq?: number
}

function isValidRoomType(type: string): type is RoomType {
  return type === "chat" || type === "game"
}

function isValidMessageType(type: string): type is MessageType {
  return (
    type === "chat" ||
    type === "action" ||
    type === "system" ||
    type === "game_response" ||
    type === "game_command"
  )
}

function toRoom(raw: RoomSummaryResponse): Room {
  return {
    id: raw.id,
    room_number: raw.room_number,
    name: raw.name,
    type: isValidRoomType(raw.type) ? raw.type : "chat",
    description: raw.description,
    is_private: raw.is_private,
    max_members: raw.max_members,
    slow_mode_sec: raw.slow_mode_sec,
    owner_nickname: raw.owner_nickname,
    user_count: raw.user_count,
  }
}

function toMessage(raw: MessageResponse): Message {
  return {
    id: raw.id,
    room_id: raw.room_id,
    nickname: raw.nickname,
    text: raw.text,
    msg_type: isValidMessageType(raw.msg_type) ? raw.msg_type : "chat",
    seq: raw.seq,
    created_at: raw.created_at,
  }
}

export function sanitizeMessage(raw: {
  id: string
  room_id: string
  nickname: string
  text: string
  msg_type: string
  seq: number
  created_at: number
}): Message {
  return toMessage(raw)
}

interface FetchMessageOptions {
  since_seq?: number
  limit?: number
}

export interface CreateRoomOptions {
  name: string
  description?: string
  password?: string
  max_members?: number
  slow_mode_sec?: number
}

export async function fetchRooms(
  serverUrl: string,
  token: string,
  query?: string,
): Promise<Room[]> {
  const params =
    query !== undefined && query.length > 0
      ? `?q=${encodeURIComponent(query)}`
      : ""
  const response = await fetch(`${serverUrl}/rooms${params}`, {
    headers: { authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw new Error(`Failed to list rooms: ${response.status.toString()}`)
  }
  const data = (await response.json()) as RoomSummaryResponse[]
  return data.map((raw) => toRoom(raw))
}

export async function getRoom(
  serverUrl: string,
  roomId: string,
  token: string,
): Promise<Room> {
  const response = await fetch(`${serverUrl}/rooms/${roomId}`, {
    headers: { authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw new Error(`Failed to get room: ${response.status.toString()}`)
  }
  const raw = (await response.json()) as RoomSummaryResponse
  return toRoom(raw)
}

export async function joinRoom(
  serverUrl: string,
  roomId: string,
  token: string,
  password?: string,
): Promise<void> {
  const response = await fetch(`${serverUrl}/rooms/${roomId}/join`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ password: password ?? null }),
  })
  if (!response.ok) {
    const detail = await response
      .json()
      .then((d: { detail?: string }) => d.detail ?? "")
      .catch(() => "")
    throw new Error(detail || `Failed to join: ${response.status.toString()}`)
  }
}

export async function leaveRoom(
  serverUrl: string,
  roomId: string,
  token: string,
): Promise<void> {
  const response = await fetch(`${serverUrl}/rooms/${roomId}/leave`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw new Error(`Failed to leave: ${response.status.toString()}`)
  }
}

export async function createRoom(
  serverUrl: string,
  token: string,
  options: CreateRoomOptions,
): Promise<Room> {
  const response = await fetch(`${serverUrl}/rooms`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      name: options.name,
      description: options.description ?? "",
      password: options.password ?? null,
      max_members: options.max_members ?? null,
      slow_mode_sec: options.slow_mode_sec ?? 0,
    }),
  })
  if (!response.ok) {
    const detail = await response
      .json()
      .then((d: { detail?: string }) => d.detail ?? "")
      .catch(() => "")
    throw new Error(
      detail || `Failed to create room: ${response.status.toString()}`,
    )
  }
  const raw = (await response.json()) as RoomSummaryResponse
  return toRoom(raw)
}

export async function fetchMessages(
  serverUrl: string,
  roomId: string,
  token: string,
  options?: FetchMessageOptions,
): Promise<Message[]> {
  const parameters = new URLSearchParams()
  if (options?.since_seq !== undefined) {
    parameters.set("since_seq", options.since_seq.toString())
  }
  if (options?.limit !== undefined) {
    parameters.set("limit", options.limit.toString())
  }

  const query = parameters.toString()
  const queryString = query ? `?${query}` : ""
  const url = `${serverUrl}/rooms/${roomId}/messages${queryString}`

  const response = await fetch(url, {
    headers: { authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch messages: ${response.status.toString()}`)
  }
  const data = (await response.json()) as MessageResponse[]
  return data.map((raw) => toMessage(raw))
}

export async function sendMessage(
  serverUrl: string,
  roomId: string,
  token: string,
  text: string,
): Promise<{ ok: boolean; id: string; seq: number }> {
  const response = await fetch(`${serverUrl}/rooms/${roomId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ text }),
  })
  if (!response.ok) {
    throw new Error(`${String(response.status)}: ${response.statusText}`)
  }
  const data = (await response.json()) as SendMessageResponse
  return {
    ok: true,
    id: data.id ?? "",
    seq: data.seq ?? 0,
  }
}

export async function fetchUsers(
  serverUrl: string,
  roomId: string,
  token: string,
): Promise<string[]> {
  const response = await fetch(`${serverUrl}/rooms/${roomId}/users`, {
    headers: { authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch user list: ${response.status.toString()}`)
  }
  const data = (await response.json()) as { nickname: string }[]
  return data.map((user) => user.nickname)
}

export async function fetchUsersWithIds(
  serverUrl: string,
  roomId: string,
  token: string,
): Promise<{ id: string; nickname: string }[]> {
  const response = await fetch(`${serverUrl}/rooms/${roomId}/users`, {
    headers: { authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    throw new Error(`Failed to fetch user list: ${response.status.toString()}`)
  }
  const data = (await response.json()) as { id: string; nickname: string }[]
  return data.map((user) => ({ id: user.id, nickname: user.nickname }))
}

export async function fetchMutedUserIds(
  serverUrl: string,
  roomId: string,
  token: string,
): Promise<string[]> {
  const response = await fetch(`${serverUrl}/rooms/${roomId}/mutes`, {
    headers: { authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    // Non-owners get 403; treat as empty mute list
    return []
  }
  const data = (await response.json()) as { user_id: string }[]
  return data.map((m) => m.user_id)
}

export async function muteUser(
  serverUrl: string,
  roomId: string,
  token: string,
  userId: string,
  reason = "",
): Promise<void> {
  const response = await fetch(`${serverUrl}/rooms/${roomId}/mutes`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ user_id: userId, reason }),
  })
  if (!response.ok) {
    const detail = await response
      .json()
      .then((d: { detail?: string }) => d.detail ?? "")
      .catch(() => "")
    throw new Error(detail || `Failed to mute: ${response.status.toString()}`)
  }
}

export async function unmuteUser(
  serverUrl: string,
  roomId: string,
  token: string,
  userId: string,
): Promise<void> {
  const response = await fetch(`${serverUrl}/rooms/${roomId}/mutes/${userId}`, {
    method: "DELETE",
    headers: { authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    const detail = await response
      .json()
      .then((d: { detail?: string }) => d.detail ?? "")
      .catch(() => "")
    throw new Error(detail || `Failed to unmute: ${response.status.toString()}`)
  }
}

export async function fetchBannedUsers(
  serverUrl: string,
  roomId: string,
  token: string,
): Promise<{ user_id: string; nickname: string }[]> {
  const response = await fetch(`${serverUrl}/rooms/${roomId}/bans`, {
    headers: { authorization: `Bearer ${token}` },
  })
  if (!response.ok) return []
  const data = (await response.json()) as {
    user_id: string
    nickname: string
  }[]
  return data.map((b) => ({ user_id: b.user_id, nickname: b.nickname }))
}

export async function banUser(
  serverUrl: string,
  roomId: string,
  token: string,
  userId: string,
  reason = "",
): Promise<void> {
  const response = await fetch(`${serverUrl}/rooms/${roomId}/bans`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ user_id: userId, reason }),
  })
  if (!response.ok) {
    const detail = await response
      .json()
      .then((d: { detail?: string }) => d.detail ?? "")
      .catch(() => "")
    throw new Error(detail || `Failed to ban: ${response.status.toString()}`)
  }
}

export async function unbanUser(
  serverUrl: string,
  roomId: string,
  token: string,
  userId: string,
): Promise<void> {
  const response = await fetch(`${serverUrl}/rooms/${roomId}/bans/${userId}`, {
    method: "DELETE",
    headers: { authorization: `Bearer ${token}` },
  })
  if (!response.ok) {
    const detail = await response
      .json()
      .then((d: { detail?: string }) => d.detail ?? "")
      .catch(() => "")
    throw new Error(detail || `Failed to unban: ${response.status.toString()}`)
  }
}

export async function markRead(
  serverUrl: string,
  roomId: string,
  token: string,
): Promise<void> {
  await fetch(`${serverUrl}/rooms/${roomId}/read`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}` },
  })
}
