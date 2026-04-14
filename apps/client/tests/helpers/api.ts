import { execSync } from "node:child_process"

const BASE = "http://localhost:7799"
const DATABASE_URL =
  process.env["CHATTY_DATABASE_URL"] ?? "postgresql://localhost/chatty"

export interface TestUser {
  userId: string
  nickname: string
  token: string
}

interface QuickLoginResponse {
  access_token: string
}

interface MeResponse {
  id: string
  nickname: string
  is_admin: boolean
}

export async function quickLogin(nickname: string): Promise<TestUser> {
  const response = await fetch(`${BASE}/auth/quick-login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nickname }),
  })
  if (!response.ok)
    throw new Error(`quick-login failed: ${await response.text()}`)
  const data = (await response.json()) as QuickLoginResponse
  const token = data.access_token

  const meResponse = await fetch(`${BASE}/auth/me`, {
    headers: { authorization: `Bearer ${token}` },
  })
  if (!meResponse.ok) throw new Error(`me failed: ${await meResponse.text()}`)
  const me = (await meResponse.json()) as MeResponse

  return { userId: me.id, nickname: me.nickname, token }
}

export async function createAdminUser(nickname: string): Promise<TestUser> {
  const user = await quickLogin(nickname)
  execSync(
    `psql "${DATABASE_URL}" -c "UPDATE users SET is_admin = TRUE WHERE id = '${user.userId}'"`,
  )
  // Re-login to refresh token with admin flag
  return quickLogin(nickname)
}

export async function login(nickname: string): Promise<string> {
  const user = await quickLogin(nickname)
  return user.token
}

interface SendMessageResponse {
  id: string
}

export async function sendMessage(
  token: string,
  roomId: string,
  text: string,
): Promise<string> {
  const response = await fetch(`${BASE}/rooms/${roomId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ text }),
  })
  if (!response.ok)
    throw new Error(`sendMessage failed: ${await response.text()}`)
  const data = (await response.json()) as SendMessageResponse
  return data.id
}

export async function banUser(
  adminToken: string,
  roomId: string,
  userId: string,
  durationSec?: number,
): Promise<void> {
  const response = await fetch(`${BASE}/rooms/${roomId}/bans`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${adminToken}`,
    },
    body: JSON.stringify({
      user_id: userId,
      reason: "test",
      duration_sec: durationSec ?? undefined,
    }),
  })
  if (!response.ok) throw new Error(`banUser failed: ${await response.text()}`)
}

export async function muteUser(
  adminToken: string,
  roomId: string,
  userId: string,
  durationSec = 60,
): Promise<void> {
  const response = await fetch(`${BASE}/rooms/${roomId}/mutes`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${adminToken}`,
    },
    body: JSON.stringify({
      user_id: userId,
      reason: "test",
      duration_sec: durationSec,
    }),
  })
  if (!response.ok) throw new Error(`muteUser failed: ${await response.text()}`)
}
