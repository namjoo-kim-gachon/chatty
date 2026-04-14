import { readFileSync, existsSync } from "node:fs"
import { fileURLToPath } from "node:url"
import path from "node:path"
import type { Locale } from "./types.js"
import { defaultLocale } from "./default.js"

const LOCALES_DIR = path.resolve(
  fileURLToPath(import.meta.url),
  "../../../locales",
)

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
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

function mergeLocale(base: Locale, override: unknown): Locale {
  if (!isRecord(override)) return base
  return {
    status: mergeSection(base.status, override["status"]),
    app: mergeSection(base.app, override["app"]),
    message: mergeSection(base.message, override["message"]),
    commands: mergeSection(base.commands, override["commands"]),
    roomList: mergeSection(base.roomList, override["roomList"]),
    createRoom: mergeSection(base.createRoom, override["createRoom"]),
    userList: mergeSection(base.userList, override["userList"]),
    passwordInput: mergeSection(base.passwordInput, override["passwordInput"]),
    login: mergeSection(base.login, override["login"]),
  }
}

export function loadLocale(name: string | undefined): Locale {
  if (name === undefined || name === "en") return defaultLocale

  const filePath = path.join(LOCALES_DIR, `${name}.json`)
  if (!existsSync(filePath)) return defaultLocale

  try {
    const raw = JSON.parse(readFileSync(filePath, "utf8")) as unknown
    return mergeLocale(defaultLocale, raw)
  } catch {
    return defaultLocale
  }
}
