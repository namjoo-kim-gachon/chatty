import { readFileSync, existsSync } from "node:fs"
import { homedir } from "node:os"
import path from "node:path"
import type { Theme } from "./types.js"
import { defaultTheme } from "./default.js"
import { draculaTheme } from "./dracula.js"

const BUILTIN: Record<string, Theme> = {
  default: defaultTheme,
  dracula: draculaTheme,
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined
}

function asStringArray(value: unknown): readonly string[] | undefined {
  if (!Array.isArray(value)) return undefined
  const result = value.filter(
    (item): item is string => typeof item === "string",
  )
  return result.length > 0 ? result : undefined
}

function mergeSection<T extends Record<string, string>>(
  base: T,
  override: unknown,
): T {
  if (!isRecord(override)) return base
  const result: Record<string, string> = {}
  for (const key of Object.keys(base)) {
    const overrideValue = override[key]
    result[key] =
      typeof overrideValue === "string"
        ? overrideValue
        : String(base[key as keyof T])
  }
  return result as T
}

function mergeMessage(
  base: Theme["message"],
  override: unknown,
): Theme["message"] {
  if (!isRecord(override)) return base
  return {
    system: asString(override["system"]) ?? base.system,
    gameResponse: asString(override["gameResponse"]) ?? base.gameResponse,
    action: asString(override["action"]) ?? base.action,
    selfNick: asString(override["selfNick"]) ?? base.selfNick,
    nickColors: asStringArray(override["nickColors"]) ?? base.nickColors,
  }
}

function mergeTheme(base: Theme, override: unknown): Theme {
  if (!isRecord(override)) return base
  return {
    status: mergeSection(base.status, override["status"]),
    message: mergeMessage(base.message, override["message"]),
    ui: mergeSection(base.ui, override["ui"]),
    symbols: mergeSection(base.symbols, override["symbols"]),
  }
}

export function loadTheme(name: string | undefined): Theme {
  if (name === undefined || name === "default") return defaultTheme

  const builtin = BUILTIN[name]
  if (builtin !== undefined) return builtin

  const filePath = path.join(
    homedir(),
    ".config",
    "chatty",
    "themes",
    `${name}.json`,
  )
  if (!existsSync(filePath)) return defaultTheme

  try {
    const raw = JSON.parse(readFileSync(filePath, "utf8")) as unknown
    return mergeTheme(defaultTheme, raw)
  } catch {
    return defaultTheme
  }
}
