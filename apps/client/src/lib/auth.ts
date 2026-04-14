import type { AuthState } from "../types.js"

export interface OAuthStartResult {
  url: string
  state: string
}

export type OAuthPollStatus = "pending" | "complete" | "error"

export interface OAuthUser {
  id: string
  email: string
  nickname: string
  is_admin: boolean
  created_at: number
}

export interface OAuthPollResult {
  status: OAuthPollStatus
  access_token?: string
  refresh_token?: string
  user?: OAuthUser
  is_new_user?: boolean
  suggested_nickname?: string
  error?: string
}

export async function startOAuth(serverUrl: string): Promise<OAuthStartResult> {
  const resp = await fetch(`${serverUrl}/auth/google/start`)
  if (!resp.ok) {
    throw new Error(`Failed to start OAuth: ${resp.statusText}`)
  }
  return (await resp.json()) as OAuthStartResult
}

export async function pollOAuth(
  serverUrl: string,
  state: string,
): Promise<OAuthPollResult> {
  const resp = await fetch(`${serverUrl}/auth/poll/${state}`)
  if (!resp.ok) {
    throw new Error(`Poll request failed: ${resp.statusText}`)
  }
  return (await resp.json()) as OAuthPollResult
}

export async function refreshToken(
  serverUrl: string,
  rt: string,
): Promise<{ access_token: string; refresh_token: string } | null> {
  try {
    const resp = await fetch(`${serverUrl}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    })
    if (!resp.ok) return null
    return (await resp.json()) as {
      access_token: string
      refresh_token: string
    }
  } catch {
    return null
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

export async function setNickname(
  serverUrl: string,
  token: string,
  nickname: string,
): Promise<OAuthUser> {
  const resp = await fetch(`${serverUrl}/auth/me/nickname`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ nickname }),
  })
  if (!resp.ok) {
    const text = await resp.text()
    throw new ApiError(`Failed to set nickname: ${text}`, resp.status)
  }
  return (await resp.json()) as OAuthUser
}

export async function logout(serverUrl: string, token: string): Promise<void> {
  try {
    await fetch(`${serverUrl}/auth/logout`, {
      method: "POST",
      headers: { authorization: `Bearer ${token}` },
    })
  } catch {
    // best-effort
  }
}

export function buildAuthState(
  user: OAuthUser,
  accessToken: string,
  rt: string,
): AuthState {
  return {
    token: accessToken,
    refresh_token: rt,
    user_id: user.id,
    nickname: user.nickname,
    is_admin: user.is_admin,
  }
}
