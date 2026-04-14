import { quickLogin, createAdminUser as apiCreateAdminUser } from "./api.js"
import type { TestUser } from "./api.js"
import { mkdtempSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import path from "node:path"
import type { TmuxHarness } from "./harness.js"

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function uniqueId(prefix: string): string {
  const timestamp = Date.now().toString(36)
  // eslint-disable-next-line sonarjs/pseudo-random
  const random = Math.random().toString(36).slice(2, 7)
  return `${prefix}${timestamp}${random}`
}

export async function createTestUser(prefix = "u"): Promise<TestUser> {
  const id = uniqueId(prefix)
  return quickLogin(id)
}

export async function createAdminTestUser(prefix = "admin"): Promise<TestUser> {
  const id = uniqueId(prefix)
  return apiCreateAdminUser(id)
}

export function createConfig(
  _user: TestUser,
  overrides: Record<string, unknown> = {},
): string {
  const directory = mkdtempSync(path.join(tmpdir(), "chatty-test-"))
  const config = {
    server_url: "http://localhost:7799",
    keybindings: {
      next_room: "ctrl+r",
      prev_room: "ctrl+shift+r",
      scroll_up: "pageup",
      scroll_down: "pagedown",
      scroll_bottom: "end",
    },
    reconnect: { max_attempts: 3, base_delay_ms: 500, max_delay_ms: 5000 },
    ...overrides,
  }
  const configPath = path.join(directory, "config.json")
  writeFileSync(configPath, JSON.stringify(config))
  return configPath
}

export async function loginTui(
  tui: TmuxHarness,
  nickname: string,
): Promise<void> {
  await tui.waitForText("nickname:", 10_000)
  tui.type(nickname)
  await sleep(100)
  tui.press("enter")
  await tui.waitForText("* connected", 15_000)
}
