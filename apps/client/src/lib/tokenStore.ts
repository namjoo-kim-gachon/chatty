import { mkdirSync, readFileSync, unlinkSync, writeFileSync } from "node:fs"
import { homedir } from "node:os"
import path from "node:path"

import type { AuthState } from "../types.js"

const TOKEN_DIR = path.join(homedir(), ".config", "chatty")
const TOKEN_FILE = path.join(TOKEN_DIR, "token.json")

const MS_PER_SECOND = 1000
const EXPIRY_BUFFER_SECONDS = 60

interface StoredTokenData {
  token: string
  refresh_token: string
  user_id: string
  needs_nickname?: boolean | undefined
}

interface JwtPayload {
  sub: string
  nickname: string
  is_admin: boolean
  exp: number
}

function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const payload = token.split(".")[1]
    if (payload === undefined) return null
    return JSON.parse(
      Buffer.from(payload, "base64url").toString("utf8"),
    ) as JwtPayload
  } catch {
    return null
  }
}

export function getNicknameFromToken(token: string): string {
  return decodeJwtPayload(token)?.nickname ?? ""
}

export function getIsAdminFromToken(token: string): boolean {
  return decodeJwtPayload(token)?.is_admin ?? false
}

export function readTokens(): AuthState | null {
  try {
    const content = readFileSync(TOKEN_FILE, "utf8")
    const stored = JSON.parse(content) as StoredTokenData
    return {
      token: stored.token,
      refresh_token: stored.refresh_token,
      user_id: stored.user_id,
      nickname: getNicknameFromToken(stored.token),
      is_admin: getIsAdminFromToken(stored.token),
      needs_nickname: stored.needs_nickname,
    }
  } catch {
    return null
  }
}

export function writeTokens(state: AuthState): void {
  mkdirSync(TOKEN_DIR, { recursive: true })
  const stored: StoredTokenData = {
    token: state.token,
    refresh_token: state.refresh_token,
    user_id: state.user_id,
    needs_nickname: state.needs_nickname,
  }
  writeFileSync(TOKEN_FILE, JSON.stringify(stored, null, 2), { mode: 0o600 })
}

export function clearTokens(): void {
  try {
    unlinkSync(TOKEN_FILE)
  } catch {
    // ignore if file doesn't exist
  }
}

export function isAccessTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token)
  if (payload === null) return true
  return Date.now() / MS_PER_SECOND > payload.exp - EXPIRY_BUFFER_SECONDS
}
