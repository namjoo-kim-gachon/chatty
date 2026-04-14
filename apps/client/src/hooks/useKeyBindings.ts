import { useInput } from "ink"
import type { Config } from "../types.js"

interface InkKeyInput {
  ctrl?: boolean
  shift?: boolean
  meta?: boolean
  key?: string
}

export type KeyAction =
  | "next_room"
  | "prev_room"
  | "scroll_up"
  | "scroll_down"
  | "scroll_bottom"

const KEY_MAP: Record<string, string> = {
  pageup: "pageUp",
  pagedown: "pageDown",
  end: "end",
  home: "home",
  up: "upArrow",
  down: "downArrow",
  left: "leftArrow",
  right: "rightArrow",
}

export function parseKeyBinding(binding: string): InkKeyInput {
  const parts = binding.toLowerCase().split("+")
  const result: InkKeyInput = {}

  const modifiers = parts.slice(0, -1)
  const key = parts.at(-1)

  for (const modifier of modifiers) {
    if (modifier === "ctrl") result.ctrl = true
    if (modifier === "shift") result.shift = true
    if (modifier === "meta" || modifier === "alt") result.meta = true
  }

  result.key = key === undefined ? "" : (KEY_MAP[key] ?? key)
  return result
}

function matchesBinding(
  binding: string,
  input: string,
  key: {
    ctrl: boolean
    shift: boolean
    meta: boolean
    pageUp: boolean
    pageDown: boolean
  },
): boolean {
  const parsed = parseKeyBinding(binding)
  if (parsed.ctrl === true && !key.ctrl) return false
  if (parsed.shift === true && !key.shift) return false
  if (parsed.meta === true && !key.meta) return false
  if (parsed.key === undefined || parsed.key === "") return false
  if (parsed.key === "pageUp") return key.pageUp
  if (parsed.key === "pageDown") return key.pageDown
  return (
    input.toLowerCase() === parsed.key ||
    (key.ctrl && input.toLowerCase() === parsed.key)
  )
}

interface UseKeyBindingsOptions {
  readonly onAction: (action: KeyAction) => void
}

export function useKeyBindings(
  config: Config,
  options: UseKeyBindingsOptions,
): void {
  const { onAction } = options

  useInput((input, key) => {
    if (key.pageUp) {
      onAction("scroll_up")
      return
    }
    if (key.pageDown) {
      onAction("scroll_down")
      return
    }

    const bindings = config.keybindings
    const keyState = {
      ctrl: key.ctrl,
      shift: key.shift,
      meta: key.meta,
      pageUp: key.pageUp,
      pageDown: key.pageDown,
    }

    if (
      bindings["next_room"] !== undefined &&
      matchesBinding(bindings["next_room"], input, keyState)
    ) {
      onAction("next_room")
      return
    }
    if (
      bindings["prev_room"] !== undefined &&
      matchesBinding(bindings["prev_room"], input, keyState)
    ) {
      onAction("prev_room")
      return
    }
    if (
      bindings["scroll_bottom"] !== undefined &&
      matchesBinding(bindings["scroll_bottom"], input, keyState)
    ) {
      onAction("scroll_bottom")
    }
  })
}
