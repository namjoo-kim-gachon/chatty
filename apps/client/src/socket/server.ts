import { createServer } from "node:net"
import type { Server, Socket } from "node:net"
import { appBridge } from "../bridge.js"
import { parseRequest } from "./protocol.js"
import type { SocketResponse } from "./protocol.js"
import { handlers } from "./handlers.js"

const DEFAULT_PORT = 7800
const ENV_PORT_KEY = "CHATTY_SOCKET_PORT"

function createLineBuffer(
  onLine: (line: string) => void,
): (chunk: Buffer) => void {
  let buffer = ""
  return (chunk: Buffer) => {
    buffer += chunk.toString("utf8")
    const lines = buffer.split("\n")
    buffer = lines.pop() ?? ""
    for (const line of lines) {
      const trimmed = line.trim()
      if (trimmed.length > 0) {
        onLine(trimmed)
      }
    }
  }
}

function writeResponse(socket: Socket, response: SocketResponse): void {
  try {
    socket.write(JSON.stringify(response) + "\n")
  } catch {
    // socket may be closed
  }
}

async function handleLine(line: string, socket: Socket): Promise<void> {
  const result = parseRequest(line)

  if ("error" in result) {
    writeResponse(socket, { id: "", ok: false, error: result.error })
    return
  }

  const { request } = result

  if (!appBridge.isReady) {
    writeResponse(socket, {
      id: request.id,
      ok: false,
      error: "TUI not ready: user not logged in",
    })
    return
  }

  const state = appBridge.getState()
  const actions = appBridge.getActions()

  if (state === undefined || actions === undefined) {
    writeResponse(socket, {
      id: request.id,
      ok: false,
      error: "TUI state unavailable",
    })
    return
  }

  const handler = handlers[request.command]
  try {
    const data = await handler(
      state,
      actions,
      request.params ?? {},
      state.config,
      state.authState,
    )
    writeResponse(socket, { id: request.id, ok: true, data })
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error"
    writeResponse(socket, { id: request.id, ok: false, error: message })
  }
}

export function startSocketServer(): Server {
  const portEnvironment = process.env[ENV_PORT_KEY]
  const port =
    portEnvironment === undefined ? DEFAULT_PORT : Number(portEnvironment)

  const server = createServer((socket: Socket) => {
    const processLine = createLineBuffer((line: string) => {
      void handleLine(line, socket)
    })
    socket.on("data", processLine)
    socket.on("error", () => {
      // ignore client disconnect errors
    })
  })

  server.listen(port, "127.0.0.1")

  server.on("error", (err: NodeJS.ErrnoException) => {
    if (err.code === "EADDRINUSE") {
      process.stderr.write(
        `chatty: socket server port ${port.toString()} already in use\n`,
      )
    }
  })

  return server
}
