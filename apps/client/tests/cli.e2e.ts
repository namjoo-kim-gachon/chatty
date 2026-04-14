import { describe, test, expect } from "vitest"
import { TmuxHarness } from "./helpers/harness.js"
import { createTestUser, createConfig, loginTui } from "./helpers/fixtures.js"
import { nextPort, runCli, runCliJson, waitForSocket } from "./helpers/cli.js"
import type { Room, Message } from "../src/types.js"

interface StatusResponse {
  nickname: string
  user_id: string
  is_admin: boolean
  active_room: Room | null
  sse_status: string
  is_muted: boolean
  is_banned: boolean
}

describe("chatty-cli", () => {
  test("status: shows login info and active room", async () => {
    const port = nextPort()
    const user = await createTestUser("cli")
    const tui = new TmuxHarness(createConfig(user), {
      env: { CHATTY_SOCKET_PORT: port.toString() },
    })

    try {
      await loginTui(tui, user.nickname)
      await waitForSocket(port)

      const status = runCliJson(port, "status") as StatusResponse
      expect(status.nickname).toBe(user.nickname)
      expect(status.active_room).not.toBeNull()
      expect(status.sse_status).toBe("connected")
      expect(status.is_muted).toBe(false)
      expect(status.is_banned).toBe(false)
    } finally {
      await tui.kill()
    }
  })

  test("rooms list: returns room array", async () => {
    const port = nextPort()
    const user = await createTestUser("cli")
    const tui = new TmuxHarness(createConfig(user), {
      env: { CHATTY_SOCKET_PORT: port.toString() },
    })

    try {
      await loginTui(tui, user.nickname)
      await waitForSocket(port)

      const rooms = runCliJson(port, "rooms list") as Room[]
      expect(Array.isArray(rooms)).toBe(true)
      expect(rooms.length).toBeGreaterThan(0)
    } finally {
      await tui.kill()
    }
  })

  test("messages send + list: send and read back", async () => {
    const port = nextPort()
    const user = await createTestUser("cli")
    const tui = new TmuxHarness(createConfig(user), {
      env: { CHATTY_SOCKET_PORT: port.toString() },
    })

    try {
      await loginTui(tui, user.nickname)
      await waitForSocket(port)

      const uniqueText = `cli-msg-${Date.now().toString()}`
      runCliJson(port, `messages send ${uniqueText}`)

      // Wait for SSE to deliver the message back to TUI
      await tui.waitForText(uniqueText)

      const messages = runCliJson(port, "messages list --limit 10") as Message[]
      const found = messages.some((m) => m.text === uniqueText)
      expect(found).toBe(true)
    } finally {
      await tui.kill()
    }
  })

  test("rooms create + join: creates room and switches TUI", async () => {
    const port = nextPort()
    const user = await createTestUser("cli")
    const tui = new TmuxHarness(createConfig(user), {
      env: { CHATTY_SOCKET_PORT: port.toString() },
    })

    try {
      await loginTui(tui, user.nickname)
      await waitForSocket(port)

      const roomName = `cli-room-${Date.now().toString(36)}`
      const created = runCliJson(
        port,
        `rooms create --name ${roomName}`,
      ) as Room
      expect(created.name).toBe(roomName)

      runCliJson(port, `rooms join ${created.id}`)

      // Verify TUI switched to the new room
      await tui.waitForText(roomName)

      const status = runCliJson(port, "status") as StatusResponse
      expect(status.active_room?.id).toBe(created.id)
    } finally {
      await tui.kill()
    }
  })

  test("rooms leave: returns to waiting room", async () => {
    const port = nextPort()
    const user = await createTestUser("cli")
    const tui = new TmuxHarness(createConfig(user), {
      env: { CHATTY_SOCKET_PORT: port.toString() },
    })

    try {
      await loginTui(tui, user.nickname)
      await waitForSocket(port)

      // First join a non-waiting room
      const rooms = runCliJson(port, "rooms list") as Room[]
      const general = rooms.find((r) => r.name === "#general")
      if (general !== undefined) {
        runCliJson(port, `rooms join ${general.id}`)
        await tui.waitForText("#general")
      }

      runCliJson(port, "rooms leave")

      const status = runCliJson(port, "status") as StatusResponse
      expect(status.active_room?.id).toBe("waiting")
    } finally {
      await tui.kill()
    }
  })

  test("users list: includes current user", async () => {
    const port = nextPort()
    const user = await createTestUser("cli")
    const tui = new TmuxHarness(createConfig(user), {
      env: { CHATTY_SOCKET_PORT: port.toString() },
    })

    try {
      await loginTui(tui, user.nickname)
      await waitForSocket(port)

      const users = runCliJson(port, "users list") as string[]
      expect(users).toContain(user.nickname)
    } finally {
      await tui.kill()
    }
  })

  test("rooms info: returns current room details", async () => {
    const port = nextPort()
    const user = await createTestUser("cli")
    const tui = new TmuxHarness(createConfig(user), {
      env: { CHATTY_SOCKET_PORT: port.toString() },
    })

    try {
      await loginTui(tui, user.nickname)
      await waitForSocket(port)

      const info = runCliJson(port, "rooms info") as Room
      expect(info.id).toBeTruthy()
      expect(info.name).toBeTruthy()
    } finally {
      await tui.kill()
    }
  })

  test("connection refused: clear error when TUI not running", () => {
    const port = nextPort()
    const { stdout, exitCode } = runCli(port, "status")
    expect(exitCode).toBe(1)
    expect(stdout).toContain("Cannot connect")
  })
})
