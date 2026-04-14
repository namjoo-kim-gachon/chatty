export type RoomType = "chat" | "game"
export type MessageType =
  | "chat"
  | "action"
  | "system"
  | "game_response"
  | "game_command"
export type SSEStatus = "connected" | "reconnecting" | "disconnected"

export type Screen =
  | { type: "chat" }
  | { type: "room_list" }
  | { type: "user_list" }
  | { type: "create_room" }
  | { type: "password_input"; roomId: string; roomName: string }

export interface Room {
  id: string
  room_number: number
  name: string
  type: RoomType
  description: string
  is_private: boolean
  max_members: number
  slow_mode_sec: number
  owner_nickname: string
  user_count: number
}

export interface Message {
  id: string
  room_id: string
  nickname: string
  text: string
  msg_type: MessageType
  seq: number
  created_at: number
}

export interface Config {
  server_url: string
  keybindings: Record<string, string>
  reconnect: {
    max_attempts: number
    base_delay_ms: number
    max_delay_ms: number
  }
  theme?: string
  locale?: string
}

export interface GameState {
  stage?: number
  inventory?: string[]
  game_over?: boolean
  won?: boolean
  [key: string]: unknown
}

export interface AuthState {
  token: string
  refresh_token: string
  user_id: string
  nickname: string
  is_admin: boolean
  needs_nickname?: boolean | undefined
}

export interface UserEntry {
  id: string
  nickname: string
  isMuted: boolean
}
