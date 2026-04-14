import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs"
import { homedir } from "node:os"
import path from "node:path"
import type { Config } from "./types.js"

const CONFIG_PATH =
  process.env["CHATTY_CONFIG"] ??
  path.join(homedir(), ".config", "chatty", "config.json")

const DEFAULT_CONFIG: Config = {
  server_url: "http://localhost:7799",
  keybindings: {
    scroll_up: "pageup",
    scroll_down: "pagedown",
    scroll_bottom: "end",
  },
  reconnect: {
    max_attempts: 10,
    base_delay_ms: 1000,
    max_delay_ms: 30_000,
  },
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function isStringRecord(value: unknown): value is Record<string, string> {
  return (
    isRecord(value) && Object.values(value).every((v) => typeof v === "string")
  )
}

function parseConfig(raw: unknown): Config {
  if (!isRecord(raw)) {
    return { ...DEFAULT_CONFIG }
  }

  const serverUrl =
    typeof raw["server_url"] === "string"
      ? raw["server_url"]
      : DEFAULT_CONFIG.server_url

  const keybindings = isStringRecord(raw["keybindings"])
    ? raw["keybindings"]
    : DEFAULT_CONFIG.keybindings

  const reconnectRaw = raw["reconnect"]
  const reconnect =
    isRecord(reconnectRaw) &&
    typeof reconnectRaw["max_attempts"] === "number" &&
    typeof reconnectRaw["base_delay_ms"] === "number" &&
    typeof reconnectRaw["max_delay_ms"] === "number"
      ? {
          max_attempts: reconnectRaw["max_attempts"],
          base_delay_ms: reconnectRaw["base_delay_ms"],
          max_delay_ms: reconnectRaw["max_delay_ms"],
        }
      : DEFAULT_CONFIG.reconnect

  const theme = typeof raw["theme"] === "string" ? raw["theme"] : undefined
  const locale = typeof raw["locale"] === "string" ? raw["locale"] : undefined

  return {
    server_url: serverUrl,
    keybindings,
    reconnect,
    ...(theme === undefined ? {} : { theme }),
    ...(locale === undefined ? {} : { locale }),
  }
}

function detectSystemLocale(): string {
  try {
    const tag = Intl.DateTimeFormat().resolvedOptions().locale
    return tag.split("-")[0] ?? "en"
  } catch {
    return "en"
  }
}

export function loadConfig(): Config {
  if (!existsSync(CONFIG_PATH)) {
    const configDirectory = path.dirname(CONFIG_PATH)
    mkdirSync(configDirectory, { recursive: true })
    const locale = detectSystemLocale()
    const initialConfig: Config = { ...DEFAULT_CONFIG, locale }
    writeFileSync(CONFIG_PATH, JSON.stringify(initialConfig, null, 2))
    return { ...initialConfig }
  }

  const content = readFileSync(CONFIG_PATH, "utf8")
  let raw: unknown
  try {
    raw = JSON.parse(content) as unknown
  } catch {
    return { ...DEFAULT_CONFIG }
  }

  return parseConfig(raw)
}
