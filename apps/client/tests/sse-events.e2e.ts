import { describe, test, expect } from "vitest"
import EventSource from "eventsource"
import { TmuxHarness } from "./helpers/harness.js"
import {
  createTestUser,
  createAdminTestUser,
  createConfig,
  loginTui,
} from "./helpers/fixtures.js"
import { login, sendMessage, banUser, muteUser } from "./helpers/api.js"
import { stopServer, startServer } from "./helpers/server.js"

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

describe("SSE event handling", () => {
  test("muted -> input disabled", async () => {
    const admin = await createAdminTestUser()
    const user = await createTestUser()
    const tui = new TmuxHarness(createConfig(user))
    await loginTui(tui, user.nickname)

    await muteUser(admin.token, "general", user.userId, 60)

    await tui.waitForText("[muted]")
    expect(tui.screen()).toContain("[muted]")

    await tui.kill()
  })

  test("banned -> ban message displayed", async () => {
    const admin = await createAdminTestUser()
    const user = await createTestUser()
    const tui = new TmuxHarness(createConfig(user))
    await loginTui(tui, user.nickname)

    await banUser(admin.token, "general", user.userId)

    await tui.waitForText("banned")

    await tui.kill()
  })

  test("SSE disconnect -> reconnect and recover missed messages", async () => {
    const user = await createTestUser()
    const sender = await createTestUser("sender")
    const reconnectConfig = createConfig(user, {
      reconnect: { max_attempts: 20, base_delay_ms: 300, max_delay_ms: 2000 },
    })
    const tui = new TmuxHarness(reconnectConfig)
    await loginTui(tui, user.nickname)
    await tui.waitForText("* connected")

    await stopServer()
    await tui.waitForText("* reconnecting")

    await startServer()

    const token = await login(sender.nickname)
    await sendMessage(token, "general", "message during reconnect")

    await tui.waitForText("message during reconnect", 15_000)
    await tui.waitForText("* connected", 15_000)

    await tui.kill()
  })

  test("kicked event -> reconnect", async () => {
    const user = await createTestUser()
    const tui = new TmuxHarness(createConfig(user))
    await loginTui(tui, user.nickname)
    await tui.waitForText("* connected")

    const token = await login(user.nickname)
    const sse = new EventSource(
      `http://localhost:7799/rooms/general/stream?token=${token}`,
    )
    await sleep(500)

    await sleep(1000)
    expect(tui.screen().length).toBeGreaterThan(0)

    sse.close()
    await tui.kill()
  })
})
