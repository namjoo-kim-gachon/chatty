import { describe, test, expect } from "vitest"
import { TmuxHarness } from "./helpers/harness.js"
import { createTestUser, createConfig, loginTui } from "./helpers/fixtures.js"

describe("Login", () => {
  test("enter nickname -> enter main screen", async () => {
    const user = await createTestUser()
    const configPath = createConfig(user)
    const tui = new TmuxHarness(configPath)

    await loginTui(tui, user.nickname)

    expect(tui.screen()).toContain(user.nickname)

    await tui.kill()
  })
})
