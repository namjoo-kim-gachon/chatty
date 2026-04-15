#!/usr/bin/env node
import { connect } from "node:net"
import type { SocketResponse } from "./socket/protocol.js"

const DEFAULT_PORT = 7800
const ENV_PORT_KEY = "CHATTY_SOCKET_PORT"
const SOCKET_TIMEOUT = 5000
const MAX_MEMBERS_LIMIT = 500
const MAX_SLOW_MODE_SEC = 99

// -- Help texts ---------------------------------------------------------------------

const MAIN_HELP = `chatty-cli — Control a running Chatty TUI via TCP socket

Usage: chatty-cli [options] <command>

Options:
  --pretty       Human-readable output (default: JSON)
  --port <port>  Socket port (env: CHATTY_SOCKET_PORT, default: 7800)
  --help         Show help

Commands:
  status                          Show login info and current room
  rooms list [--query <q>]        List available rooms
  rooms create --name <n>         Create a new room
  rooms join <room-number>         Join a room by number (switches TUI)
  rooms leave                     Leave current room
  rooms info                      Show current room details
  messages list [--limit <n>] [--all]  Read messages from TUI (default: 50)
  messages send <text>            Send a message to current room
  users list                      List users in current room
  users mute <nickname>           Mute a user (owner only)
  users unmute <nickname>         Unmute a user (owner only)
  users ban <nickname>            Ban a user (owner only)
  users unban <nickname>          Unban a user (owner only)
`

const ROOMS_HELP = `chatty-cli rooms — Room management commands

Usage: chatty-cli rooms <subcommand>

Subcommands:
  list [--query <q>]              List available rooms
  create --name <n> [options]     Create a new room
    --description <d>             Room description
    --password <p>                Room password (makes room private)
    --max-members <n>             Maximum members (2-500, default: 500)
    --slow-mode <sec>             Slow mode interval in seconds (0-99, default: 1)
  join <room-number> [--password <p>] Join a room by number (switches TUI)
  leave                           Leave current room
  info                            Show current room details
`

const MESSAGES_HELP = `chatty-cli messages — Message commands

Usage: chatty-cli messages <subcommand>

Subcommands:
  list [--limit <n>] [--all]      Read messages from TUI memory (default: 50)
  send <text>                     Send a message to the current room
`

const USERS_HELP = `chatty-cli users — User commands

Usage: chatty-cli users <subcommand>

Subcommands:
  list                            List users in current room
  mute <nickname>                 Mute a user (owner only)
  unmute <nickname>               Unmute a user (owner only)
  ban <nickname>                  Ban a user (owner only)
  unban <nickname>                Unban a user (owner only)
`

// -- Types --------------------------------------------------------------------------

interface CliRequest {
  id: string
  command: string
  params?: Record<string, unknown>
}

type BuildResult =
  | { kind: "request"; request: CliRequest }
  | { kind: "text"; text: string; isError: boolean }

function makeRequest(
  command: string,
  params?: Record<string, unknown>,
): BuildResult {
  const request: CliRequest = { id: "1", command }
  if (params !== undefined) {
    request.params = params
  }
  return { kind: "request", request }
}

function makeText(text: string, isError = false): BuildResult {
  return { kind: "text", text, isError }
}

// -- TCP client ---------------------------------------------------------------------

function sendCommand(
  port: number,
  request: CliRequest,
): Promise<SocketResponse> {
  return new Promise((resolve, reject) => {
    const socket = connect({ host: "127.0.0.1", port }, () => {
      socket.write(JSON.stringify(request) + "\n")
    })

    let buffer = ""
    socket.on("data", (chunk: Buffer) => {
      buffer += chunk.toString("utf8")
      const newlineIndex = buffer.indexOf("\n")
      if (newlineIndex !== -1) {
        const line = buffer.slice(0, newlineIndex)
        socket.end()
        try {
          resolve(JSON.parse(line) as SocketResponse)
        } catch {
          reject(new Error("Invalid JSON response from TUI"))
        }
      }
    })

    socket.on("error", (err: NodeJS.ErrnoException) => {
      if (err.code === "ECONNREFUSED") {
        reject(
          new Error(
            `Cannot connect to Chatty TUI on port ${port.toString()}. Is the TUI running?`,
          ),
        )
      } else {
        reject(err)
      }
    })

    socket.setTimeout(SOCKET_TIMEOUT, () => {
      socket.destroy()
      reject(new Error("Connection timed out"))
    })
  })
}

// -- Pretty printer -----------------------------------------------------------------

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return ""
  if (typeof value === "string") return value
  return JSON.stringify(value)
}

function formatObject(record: Record<string, unknown>): string {
  const entries = Object.entries(record)
  const maxKey = Math.max(...entries.map(([k]) => k.length))
  return entries
    .map(([key, value]) => {
      const paddedKey = key.padEnd(maxKey)
      return `  ${paddedKey}  ${formatValue(value)}`
    })
    .join("\n")
}

function formatPretty(data: unknown): string {
  if (data === null || data === undefined) return "null"
  if (Array.isArray(data)) {
    if (data.length === 0) return "(empty)"
    return data
      .map((item: unknown) => {
        if (typeof item === "object" && item !== null) {
          return formatObject(item as Record<string, unknown>)
        }
        return formatValue(item)
      })
      .join("\n---\n")
  }
  if (typeof data === "object") {
    return formatObject(data as Record<string, unknown>)
  }
  return formatValue(data)
}

// -- Arg parsing --------------------------------------------------------------------

interface ParsedArgs {
  pretty: boolean
  port: number
  positionals: string[]
  flags: Record<string, string>
}

function parseCliArgs(argv: string[]): ParsedArgs {
  const args = argv.slice(2) // skip node + script
  let pretty = false
  let port = Number(process.env[ENV_PORT_KEY] ?? DEFAULT_PORT.toString())
  const positionals: string[] = []
  const flags: Record<string, string> = {}

  let index = 0
  while (index < args.length) {
    const argument = args[index] ?? ""
    switch (true) {
      case argument === "--pretty": {
        pretty = true
        break
      }
      case argument === "--all": {
        flags["all"] = "true"
        break
      }
      case argument === "--port": {
        index++
        const value = args[index]
        if (value !== undefined) port = Number(value)
        break
      }
      case argument === "--help" || argument === "-h": {
        positionals.unshift("help")
        break
      }
      case argument.startsWith("--"): {
        const key = argument.slice(2)
        index++
        const value = args[index]
        if (value !== undefined) {
          flags[key] = value
        }
        break
      }
      default: {
        positionals.push(argument)
        break
      }
    }
    index++
  }

  return { pretty, port, positionals, flags }
}

// -- Command routing ----------------------------------------------------------------

function buildRoomsCreateRequest(flags: Record<string, string>): BuildResult {
  if (flags["name"] === undefined) {
    return makeText("Error: --name is required for rooms create", true)
  }
  const params: Record<string, unknown> = { name: flags["name"] }
  if (flags["description"] !== undefined) {
    params["description"] = flags["description"]
  }
  if (flags["password"] !== undefined) {
    params["password"] = flags["password"]
  }
  if (flags["max-members"] !== undefined) {
    const n = Number(flags["max-members"])
    if (n < 2 || n > MAX_MEMBERS_LIMIT) {
      return makeText(
        `Error: --max-members must be 2-${String(MAX_MEMBERS_LIMIT)}`,
        true,
      )
    }
    params["max_members"] = n
  }
  if (flags["slow-mode"] !== undefined) {
    const n = Number(flags["slow-mode"])
    if (n < 0 || n > MAX_SLOW_MODE_SEC) {
      return makeText(
        `Error: --slow-mode must be 0-${String(MAX_SLOW_MODE_SEC)}`,
        true,
      )
    }
    params["slow_mode_sec"] = n
  }
  return makeRequest("rooms.create", params)
}

function buildRoomsJoinRequest(
  positionals: string[],
  flags: Record<string, string>,
): BuildResult {
  const roomNumber = positionals[2]
  if (roomNumber === undefined) {
    return makeText("Error: room-number is required for rooms join", true)
  }
  const params: Record<string, unknown> = { room_number: roomNumber }
  if (flags["password"] !== undefined) {
    params["password"] = flags["password"]
  }
  return makeRequest("rooms.join", params)
}

function buildRoomsRequest(
  positionals: string[],
  flags: Record<string, string>,
): BuildResult {
  const sub = positionals[1] ?? ""
  switch (sub) {
    case "list": {
      const params: Record<string, unknown> = {}
      if (flags["query"] !== undefined) params["query"] = flags["query"]
      return makeRequest("rooms.list", params)
    }
    case "create": {
      return buildRoomsCreateRequest(flags)
    }
    case "join": {
      return buildRoomsJoinRequest(positionals, flags)
    }
    case "leave": {
      return makeRequest("rooms.leave")
    }
    case "info": {
      return makeRequest("rooms.info")
    }
    case "help":
    case "": {
      return makeText(ROOMS_HELP)
    }
    default: {
      return makeText(`Unknown rooms subcommand: ${sub}\n\n${ROOMS_HELP}`)
    }
  }
}

function buildMessagesRequest(
  positionals: string[],
  flags: Record<string, string>,
): BuildResult {
  const sub = positionals[1] ?? ""
  switch (sub) {
    case "list": {
      const params: Record<string, unknown> = {}
      if (flags["all"] !== undefined) {
        params["all"] = true
      } else if (flags["limit"] !== undefined) {
        params["limit"] = Number(flags["limit"])
      }
      return makeRequest("messages.list", params)
    }
    case "send": {
      const text = positionals.slice(2).join(" ")
      if (text.length === 0) {
        return makeText("Error: text is required for messages send", true)
      }
      return makeRequest("messages.send", { text })
    }
    case "help":
    case "": {
      return makeText(MESSAGES_HELP)
    }
    default: {
      return makeText(`Unknown messages subcommand: ${sub}\n\n${MESSAGES_HELP}`)
    }
  }
}

function buildUsersMuteRequest(
  positionals: string[],
  command: "users.mute" | "users.unmute" | "users.ban" | "users.unban",
): BuildResult {
  const labelMap = {
    "users.mute": "mute",
    "users.unmute": "unmute",
    "users.ban": "ban",
    "users.unban": "unban",
  }
  const label = labelMap[command]
  const nickname = positionals[2]
  if (nickname === undefined || nickname.length === 0) {
    return makeText(`Error: nickname is required for users ${label}`, true)
  }
  return makeRequest(command, { nickname })
}

function buildUsersRequest(positionals: string[]): BuildResult {
  const sub = positionals[1] ?? ""
  switch (sub) {
    case "list": {
      return makeRequest("users.list")
    }
    case "mute": {
      return buildUsersMuteRequest(positionals, "users.mute")
    }
    case "unmute": {
      return buildUsersMuteRequest(positionals, "users.unmute")
    }
    case "ban": {
      return buildUsersMuteRequest(positionals, "users.ban")
    }
    case "unban": {
      return buildUsersMuteRequest(positionals, "users.unban")
    }
    case "help":
    case "": {
      return makeText(USERS_HELP)
    }
    default: {
      return makeText(`Unknown users subcommand: ${sub}\n\n${USERS_HELP}`)
    }
  }
}

function buildRequest(
  positionals: string[],
  flags: Record<string, string>,
): BuildResult {
  const group = positionals[0] ?? ""
  switch (group) {
    case "status": {
      return makeRequest("status")
    }
    case "rooms": {
      return buildRoomsRequest(positionals, flags)
    }
    case "messages": {
      return buildMessagesRequest(positionals, flags)
    }
    case "users": {
      return buildUsersRequest(positionals)
    }
    case "help":
    case "": {
      return makeText(MAIN_HELP)
    }
    default: {
      return makeText(`Unknown command: ${group}\n\n${MAIN_HELP}`)
    }
  }
}

// -- Main ---------------------------------------------------------------------------

const { pretty, port, positionals, flags } = parseCliArgs(process.argv)
const result = buildRequest(positionals, flags)

if (result.kind === "text") {
  process.stdout.write(result.text + "\n")
  if (result.isError) {
    process.exitCode = 1
  }
} else {
  try {
    const response = await sendCommand(port, result.request)

    if (response.ok) {
      if (pretty) {
        process.stdout.write(formatPretty(response.data) + "\n")
      } else {
        process.stdout.write(JSON.stringify(response.data) + "\n")
      }
    } else {
      process.stderr.write(`Error: ${response.error}\n`)
      process.exitCode = 1
    }
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error"
    process.stderr.write(`Error: ${message}\n`)
    process.exitCode = 1
  }
}
