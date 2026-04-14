import type { AuthState, Config, Room } from "../types.js"
import type { AppState, AppActions } from "../bridge.js"
import type { CommandName } from "./protocol.js"
import {
  fetchRooms,
  createRoom,
  getRoom,
  fetchUsers,
  fetchUsersWithIds,
  muteUser,
  unmuteUser,
  banUser,
  unbanUser,
  fetchBannedUsers,
  sendMessage,
} from "../lib/client.js"

const LOBBY_ROOM_ID = "lobby"
const NO_ROOM_ERROR = "Not connected to any room"
const DEFAULT_MESSAGE_LIMIT = 50

type Handler = (
  state: AppState,
  actions: AppActions,
  params: Record<string, unknown>,
  config: Config,
  authState: AuthState,
) => Promise<unknown>

function requireActiveRoom(state: AppState): Room {
  if (state.activeRoom === undefined) {
    throw new Error(NO_ROOM_ERROR)
  }
  return state.activeRoom
}

function handleStatus(state: AppState): Promise<unknown> {
  return Promise.resolve({
    nickname: state.authState.nickname,
    user_id: state.authState.user_id,
    is_admin: state.authState.is_admin,
    active_room: state.activeRoom ?? null,
    sse_status: state.sseStatus,
    is_muted: state.isMuted,
    is_banned: state.isBanned,
  })
}

async function handleRoomsList(
  _state: AppState,
  _actions: AppActions,
  params: Record<string, unknown>,
  config: Config,
  authState: AuthState,
): Promise<unknown> {
  const query =
    typeof params["query"] === "string" ? params["query"] : undefined
  return fetchRooms(config.server_url, authState.token, query)
}

async function handleRoomsCreate(
  _state: AppState,
  _actions: AppActions,
  params: Record<string, unknown>,
  config: Config,
  authState: AuthState,
): Promise<unknown> {
  const name = params["name"]
  if (typeof name !== "string" || name.length === 0) {
    throw new Error("Missing required param: name")
  }
  const options: Parameters<typeof createRoom>[2] = { name }
  if (typeof params["description"] === "string") {
    options.description = params["description"]
  }
  if (typeof params["password"] === "string") {
    options.password = params["password"]
  }
  if (typeof params["max_members"] === "number") {
    options.max_members = params["max_members"]
  }
  if (typeof params["slow_mode_sec"] === "number") {
    options.slow_mode_sec = params["slow_mode_sec"]
  }
  return createRoom(config.server_url, authState.token, options)
}

async function handleRoomsJoin(
  _state: AppState,
  actions: AppActions,
  params: Record<string, unknown>,
  config: Config,
  authState: AuthState,
): Promise<unknown> {
  const roomNumber = params["room_number"] ?? params["room_id"]
  if (typeof roomNumber !== "string" || roomNumber.length === 0) {
    throw new Error("Missing required param: room_number")
  }
  const password =
    typeof params["password"] === "string" ? params["password"] : undefined
  const room = await getRoom(config.server_url, roomNumber, authState.token)
  await actions.enterRoom(room, password)
  return { joined: true }
}

async function handleRoomsLeave(
  state: AppState,
  actions: AppActions,
): Promise<unknown> {
  const room = requireActiveRoom(state)
  if (room.id === LOBBY_ROOM_ID) {
    throw new Error("Already in lobby")
  }
  const lobbyRoom: Room = {
    id: LOBBY_ROOM_ID,
    room_number: 0,
    name: "lobby",
    type: "chat",
    description: "Lobby -- default entry room",
    is_private: false,
    max_members: 500,
    slow_mode_sec: 1,
    owner_nickname: "",
    user_count: 0,
  }
  await actions.exitRoom()
  await actions.enterRoom(lobbyRoom)
  return { left: true }
}

function handleRoomsInfo(state: AppState): Promise<unknown> {
  const room = requireActiveRoom(state)
  return Promise.resolve(room)
}

function handleMessagesList(
  state: AppState,
  _actions: AppActions,
  params: Record<string, unknown>,
): Promise<unknown> {
  requireActiveRoom(state) // validates room exists
  if (params["all"] === true) {
    return Promise.resolve(state.messages)
  }
  const limit =
    typeof params["limit"] === "number"
      ? params["limit"]
      : DEFAULT_MESSAGE_LIMIT
  return Promise.resolve(state.messages.slice(-limit))
}

async function handleMessagesSend(
  state: AppState,
  _actions: AppActions,
  params: Record<string, unknown>,
  config: Config,
  authState: AuthState,
): Promise<unknown> {
  const room = requireActiveRoom(state)
  const text = params["text"]
  if (typeof text !== "string" || text.length === 0) {
    throw new Error("Missing required param: text")
  }
  return sendMessage(config.server_url, room.id, authState.token, text)
}

async function handleUsersList(
  state: AppState,
  _actions: AppActions,
  _params: Record<string, unknown>,
  config: Config,
  authState: AuthState,
): Promise<unknown> {
  const room = requireActiveRoom(state)
  return fetchUsers(config.server_url, room.id, authState.token)
}

const NOT_OWNER_ERROR = "Only the room owner can mute users"
const USER_NOT_FOUND_ERROR = "User not found in this room"
const MISSING_NICKNAME_ERROR = "Missing required param: nickname"

async function handleUsersMute(
  state: AppState,
  _actions: AppActions,
  params: Record<string, unknown>,
  config: Config,
  authState: AuthState,
): Promise<unknown> {
  const room = requireActiveRoom(state)
  if (state.ownerNickname !== authState.nickname) {
    throw new Error(NOT_OWNER_ERROR)
  }
  const nickname = params["nickname"]
  if (typeof nickname !== "string" || nickname.length === 0) {
    throw new Error(MISSING_NICKNAME_ERROR)
  }
  const users = await fetchUsersWithIds(
    config.server_url,
    room.id,
    authState.token,
  )
  const target = users.find((u) => u.nickname === nickname)
  if (target === undefined) {
    throw new Error(USER_NOT_FOUND_ERROR)
  }
  await muteUser(config.server_url, room.id, authState.token, target.id)
  return { muted: true, nickname }
}

async function handleUsersUnmute(
  state: AppState,
  _actions: AppActions,
  params: Record<string, unknown>,
  config: Config,
  authState: AuthState,
): Promise<unknown> {
  const room = requireActiveRoom(state)
  if (state.ownerNickname !== authState.nickname) {
    throw new Error(NOT_OWNER_ERROR)
  }
  const nickname = params["nickname"]
  if (typeof nickname !== "string" || nickname.length === 0) {
    throw new Error(MISSING_NICKNAME_ERROR)
  }
  const users = await fetchUsersWithIds(
    config.server_url,
    room.id,
    authState.token,
  )
  const target = users.find((u) => u.nickname === nickname)
  if (target === undefined) {
    throw new Error(USER_NOT_FOUND_ERROR)
  }
  await unmuteUser(config.server_url, room.id, authState.token, target.id)
  return { unmuted: true, nickname }
}

async function handleUsersBan(
  state: AppState,
  _actions: AppActions,
  params: Record<string, unknown>,
  config: Config,
  authState: AuthState,
): Promise<unknown> {
  const room = requireActiveRoom(state)
  if (state.ownerNickname !== authState.nickname) {
    throw new Error(NOT_OWNER_ERROR)
  }
  const nickname = params["nickname"]
  if (typeof nickname !== "string" || nickname.length === 0) {
    throw new Error(MISSING_NICKNAME_ERROR)
  }
  const users = await fetchUsersWithIds(
    config.server_url,
    room.id,
    authState.token,
  )
  const target = users.find((u) => u.nickname === nickname)
  if (target === undefined) {
    throw new Error(USER_NOT_FOUND_ERROR)
  }
  await banUser(config.server_url, room.id, authState.token, target.id)
  return { banned: true, nickname }
}

async function handleUsersUnban(
  state: AppState,
  _actions: AppActions,
  params: Record<string, unknown>,
  config: Config,
  authState: AuthState,
): Promise<unknown> {
  const room = requireActiveRoom(state)
  if (state.ownerNickname !== authState.nickname) {
    throw new Error(NOT_OWNER_ERROR)
  }
  const nickname = params["nickname"]
  if (typeof nickname !== "string" || nickname.length === 0) {
    throw new Error(MISSING_NICKNAME_ERROR)
  }
  const banned = await fetchBannedUsers(
    config.server_url,
    room.id,
    authState.token,
  )
  const target = banned.find((b) => b.nickname === nickname)
  if (target === undefined) {
    throw new Error(USER_NOT_FOUND_ERROR)
  }
  await unbanUser(config.server_url, room.id, authState.token, target.user_id)
  return { unbanned: true, nickname }
}

export const handlers: Record<CommandName, Handler> = {
  status: (state) => handleStatus(state),
  "rooms.list": handleRoomsList,
  "rooms.create": handleRoomsCreate,
  "rooms.join": handleRoomsJoin,
  "rooms.leave": (state, actions) => handleRoomsLeave(state, actions),
  "rooms.info": (state) => handleRoomsInfo(state),
  "messages.list": (state, actions, params) =>
    handleMessagesList(state, actions, params),
  "messages.send": handleMessagesSend,
  "users.list": handleUsersList,
  "users.mute": handleUsersMute,
  "users.unmute": handleUsersUnmute,
  "users.ban": handleUsersBan,
  "users.unban": handleUsersUnban,
}
