import { describe, test } from "vitest"
import { TmuxHarness } from "./helpers/harness.js"
import { createTestUser, createConfig, loginTui } from "./helpers/fixtures.js"

describe("Game room (MUD)", () => {
  test("command input in game room -> displayed", async () => {
    const user = await createTestUser()
    const configPath = createConfig(user, {
      rooms: ["mud"],
      default_room: "mud",
    })
    const tui = new TmuxHarness(configPath)
    await loginTui(tui, user.nickname)

    await tui.waitForText("> ")

    tui.type("look")
    tui.press("enter")

    await tui.waitForText("look")

    await tui.kill()
  })

  test("shortcut command expansion: l -> look", async () => {
    const user = await createTestUser()
    const configPath = createConfig(user, {
      rooms: ["mud"],
      default_room: "mud",
    })
    const tui = new TmuxHarness(configPath)
    await loginTui(tui, user.nickname)

    await tui.waitForText("> ")
    tui.type("l")
    tui.press("enter")

    await tui.waitForText("look")

    await tui.kill()
  })

  test("Up key -> recall previous command", async () => {
    const user = await createTestUser()
    const configPath = createConfig(user, {
      rooms: ["mud"],
      default_room: "mud",
    })
    const tui = new TmuxHarness(configPath)
    await loginTui(tui, user.nickname)

    await tui.waitForText("> ")
    tui.type("go north")
    tui.press("enter")
    await tui.waitForText("go north")

    tui.clearBuffer()
    tui.press("up")

    await tui.waitForText("go north")

    await tui.kill()
  })
})
