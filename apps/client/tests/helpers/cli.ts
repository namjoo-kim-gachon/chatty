import { execSync } from "node:child_process"
import { connect } from "node:net"
import path from "node:path"
import { fileURLToPath } from "node:url"

const fileDirectory = fileURLToPath(new URL(".", import.meta.url))
const CLIENT_ROOT = path.resolve(fileDirectory, "../..")
const REPO_ROOT = path.resolve(fileDirectory, "../../../..")
const TSX_BIN = path.join(REPO_ROOT, "node_modules", ".bin", "tsx")

let portCounter = 0

export function nextPort(): number {
  return 17_800 + (process.pid % 1000) + portCounter++
}

export function runCli(
  port: number,
  args: string,
): { stdout: string; exitCode: number } {
  try {
    const stdout = execSync(
      `'${TSX_BIN}' src/cli.ts --port ${port.toString()} ${args}`,
      {
        cwd: CLIENT_ROOT,
        encoding: "utf8",
        timeout: 10_000,
        env: { ...process.env },
      },
    )
    return { stdout: stdout.trim(), exitCode: 0 }
  } catch (error: unknown) {
    const err = error as { stdout?: string; stderr?: string; status?: number }
    const output = err.stdout ?? ""
    const errorOutput = err.stderr ?? ""
    return {
      stdout: (output.length > 0 ? output : errorOutput).trim(),
      exitCode: err.status ?? 1,
    }
  }
}

export function runCliJson(port: number, args: string): unknown {
  const { stdout, exitCode } = runCli(port, args)
  if (exitCode !== 0) {
    throw new Error(`CLI exited with code ${exitCode.toString()}: ${stdout}`)
  }
  return JSON.parse(stdout) as unknown
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function waitForSocket(
  port: number,
  timeout = 10_000,
): Promise<void> {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    const connected = await new Promise<boolean>((resolve) => {
      const socket = connect({ host: "127.0.0.1", port }, () => {
        socket.end()
        resolve(true)
      })
      socket.on("error", () => {
        resolve(false)
      })
      socket.setTimeout(500, () => {
        socket.destroy()
        resolve(false)
      })
    })
    if (connected) return
    await sleep(200)
  }
  throw new Error(
    `Socket server not ready on port ${port.toString()} after ${timeout.toString()}ms`,
  )
}
