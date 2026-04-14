import { describe, test, expect } from "vitest"
import { TmuxHarness } from "./helpers/harness.js"
import { createTestUser, createConfig, loginTui } from "./helpers/fixtures.js"
import { sendMessage } from "./helpers/api.js"

describe("Room switching", () => {
  test("Ctrl+R -> switch to next room", async () => {
    const user = await createTestUser()
    const configPath = createConfig(user, { rooms: ["general", "mud"] })
    const tui = new TmuxHarness(configPath)

    await loginTui(tui, user.nickname)
    await tui.waitForText("#general")

    tui.press("ctrlR")
    await tui.waitForText("#mud")

    expect(tui.screen()).toContain("#general")
    expect(tui.screen()).toContain("#mud")

    await tui.kill()
  })

  test("room switch preserves previous messages + loads new room", async () => {
    const user = await createTestUser()
    const sender = await createTestUser("sender")
    const configPath = createConfig(user, { rooms: ["general", "mud"] })

    const uniqueMessage = `room-switch-msg-${sender.nickname}`
    await sendMessage(sender.token, "general", uniqueMessage)

    const tui = new TmuxHarness(configPath)
    await loginTui(tui, user.nickname)
    await tui.waitForText(uniqueMessage)

    tui.press("ctrlR")
    await tui.waitForText("#mud")
    expect(tui.screen()).not.toContain(uniqueMessage)

    await tui.kill()
  })
})
