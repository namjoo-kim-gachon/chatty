const VALID_COMMANDS = [
  "status",
  "rooms.list",
  "rooms.create",
  "rooms.join",
  "rooms.leave",
  "rooms.info",
  "messages.list",
  "messages.send",
  "users.list",
  "users.mute",
  "users.unmute",
  "users.ban",
  "users.unban",
] as const

export type CommandName = (typeof VALID_COMMANDS)[number]

export interface SocketRequest {
  id: string
  command: CommandName
  params?: Record<string, unknown>
}

export interface SocketResponseOk {
  id: string
  ok: true
  data: unknown
}

export interface SocketResponseError {
  id: string
  ok: false
  error: string
}

export type SocketResponse = SocketResponseOk | SocketResponseError

function isValidCommand(value: string): value is CommandName {
  return (VALID_COMMANDS as readonly string[]).includes(value)
}

export function parseRequest(
  line: string,
): { request: SocketRequest } | { error: string } {
  let parsed: unknown
  try {
    parsed = JSON.parse(line) as unknown
  } catch {
    return { error: "Invalid JSON" }
  }

  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return { error: "Request must be a JSON object" }
  }

  const record = parsed as Record<string, unknown>

  if (typeof record["id"] !== "string" || record["id"].length === 0) {
    return { error: "Missing or invalid 'id' field" }
  }

  if (typeof record["command"] !== "string") {
    return { error: "Missing or invalid 'command' field" }
  }

  if (!isValidCommand(record["command"])) {
    return {
      error: `Unknown command: ${record["command"]}. Valid: ${VALID_COMMANDS.join(", ")}`,
    }
  }

  const params = record["params"]
  if (
    params !== undefined &&
    params !== null &&
    (typeof params !== "object" || Array.isArray(params))
  ) {
    return { error: "'params' must be a JSON object" }
  }

  const request: SocketRequest = {
    id: record["id"],
    command: record["command"],
  }
  if (typeof params === "object" && params !== null) {
    request.params = params as Record<string, unknown>
  }
  return { request }
}
