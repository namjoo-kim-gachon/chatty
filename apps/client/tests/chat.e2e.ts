import { describe, test, expect } from "vitest"
import { TmuxHarness } from "./helpers/harness.js"
import { createTestUser, createConfig, loginTui } from "./helpers/fixtures.js"
import { sendMessage } from "./helpers/api.js"

describe("Chat messages", () => {
  test("send message -> displayed on screen", async () => {
    const user = await createTestUser()
    const tui = new TmuxHarness(createConfig(user))

    await loginTui(tui, user.nickname)
    tui.type("Hello world")
    tui.press("enter")

    await tui.waitForText("Hello world")
    expect(tui.screen()).toContain(user.nickname)

    await tui.kill()
  })

  test("other user message -> received via SSE", async () => {
    const user1 = await createTestUser("sender")
    const user2 = await createTestUser("viewer")

    const tui = new TmuxHarness(createConfig(user2))
    await loginTui(tui, user2.nickname)

    const uniqueText = `sse-msg-${user1.nickname}`
    await sendMessage(user1.token, "general", uniqueText)

    await tui.waitForText(uniqueText)
    expect(tui.screen()).toContain(user1.nickname)

    await tui.kill()
  })
})
