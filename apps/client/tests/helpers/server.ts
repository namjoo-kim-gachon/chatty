import { spawn, execSync } from "node:child_process"
import type { ChildProcess } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"

const fileDirectory = fileURLToPath(new URL(".", import.meta.url))
const REPO_ROOT = path.resolve(fileDirectory, "../../../..")
const SERVER_PORT = 7799

let serverProcess: ChildProcess | undefined

function killPort(port: number): void {
  try {
    // Find and kill only the LISTENING process on the port (macOS/Linux).
    // Using -sTCP:LISTEN to avoid killing client processes with established connections.
    // Using SIGKILL for immediate termination (no graceful shutdown delay).
    execSync(
      `lsof -ti tcp:${port.toString()} -sTCP:LISTEN | xargs kill -9 2>/dev/null || true`,
    )
  } catch {
    // Ignore errors if no process found
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function waitUntilUp(port: number, timeout: number): Promise<void> {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    const ok = await fetch(`http://localhost:${port.toString()}/health`)
      .then((response) => response.ok)
      .catch(() => false)
    if (ok) return
    await sleep(200)
  }
  throw new Error(
    `Server did not start within ${timeout.toString()}ms (port ${port.toString()})`,
  )
}

async function waitUntilDown(port: number, timeout: number): Promise<void> {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    const down = await fetch(`http://localhost:${port.toString()}/health`)
      .then(() => false)
      .catch(() => true)
    if (down) return
    await sleep(100)
  }
}

export async function stopServer(): Promise<void> {
  if (serverProcess === undefined) {
    // Kill any externally-managed server on the port
    killPort(SERVER_PORT)
  } else {
    serverProcess.kill("SIGKILL")
    serverProcess = undefined
  }
  await waitUntilDown(SERVER_PORT, 5000)
}

export async function startServer(): Promise<void> {
  serverProcess = spawn(
    "uv",
    [
      "run",
      "uvicorn",
      "app.main:app",
      "--port",
      String(SERVER_PORT),
      "--app-dir",
      "apps/server",
    ],
    { cwd: REPO_ROOT, stdio: "ignore", detached: false },
  )
  serverProcess.on("error", () => {
    // Ignore process errors (e.g. on forced kill)
  })
  await waitUntilUp(SERVER_PORT, 10_000)
}

export async function restartServer(): Promise<void> {
  await stopServer()
  await startServer()
}
