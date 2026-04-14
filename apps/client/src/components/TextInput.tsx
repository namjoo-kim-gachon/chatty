import React, { useRef, useCallback } from "react"
import { Text, useInput } from "ink"
import type { Key } from "ink"

/* eslint-disable no-magic-numbers */
function charColWidth(cp: number): number {
  if (
    (cp >= 0x11_00 && cp <= 0x11_5f) ||
    (cp >= 0x2e_80 && cp <= 0x30_3e) ||
    (cp >= 0x30_41 && cp <= 0x33_bf) ||
    (cp >= 0x34_00 && cp <= 0x9f_ff) ||
    (cp >= 0xac_00 && cp <= 0xd7_af) ||
    (cp >= 0xf9_00 && cp <= 0xfa_ff) ||
    (cp >= 0xff_01 && cp <= 0xff_60) ||
    (cp >= 0xff_e0 && cp <= 0xff_e6) ||
    (cp >= 0x1_f3_00 && cp <= 0x1_fa_ff)
  ) {
    return 2
  }
  return 1
}
/* eslint-enable no-magic-numbers */

// Slice the right end of text to fit within maxCols width
function rightSlice(text: string, maxCols: number): string {
  if (maxCols <= 0) return ""
  const chars = Array.from(new Intl.Segmenter().segment(text), (s) => s.segment)
  let w = 0
  let start = chars.length
  for (let index = chars.length - 1; index >= 0; index--) {
    const cw = charColWidth(chars[index]?.codePointAt(0) ?? 0)
    if (w + cw > maxCols) break
    w += cw
    start = index
  }
  return chars.slice(start).join("")
}

interface TextInputProps {
  readonly value: string
  readonly onChange: (value: string) => void
  readonly onSubmit: (value: string) => void
  readonly mask?: string
  readonly maxCols?: number
}

export function TextInput({
  value,
  onChange,
  onSubmit,
  mask,
  maxCols,
}: TextInputProps): React.ReactElement {
  // Update refs synchronously during render so the stable handler always sees
  // the latest props without waiting for a useEffect flush.
  const valueRef = useRef(value)
  const onChangeRef = useRef(onChange)
  const onSubmitRef = useRef(onSubmit)
  valueRef.current = value
  onChangeRef.current = onChange
  onSubmitRef.current = onSubmit

  // Stable handler reference -- never recreated, so Ink's useEffect never
  // re-registers the stdin listener. Eliminates the brief window between
  // cleanup and re-registration where keystrokes (e.g. '\r') can be lost.
  const stableHandler = useCallback((input: string, key: Key) => {
    if (key.ctrl || key.meta) return

    if (key.return) {
      onSubmitRef.current(valueRef.current)
      return
    }

    if (key.backspace || key.delete) {
      const next = valueRef.current.slice(0, -1)
      valueRef.current = next
      onChangeRef.current(next)
      return
    }

    if (
      key.escape ||
      key.tab ||
      key.upArrow ||
      key.downArrow ||
      key.leftArrow ||
      key.rightArrow ||
      key.pageUp ||
      key.pageDown
    ) {
      return
    }

    if (input) {
      const next = valueRef.current + input
      valueRef.current = next
      onChangeRef.current(next)
    }
  }, [])

  useInput(stableHandler)

  const full = mask === undefined ? value : mask.repeat(value.length)
  // Fit cursor block (1 col) within maxCols
  const displayed = maxCols === undefined ? full : rightSlice(full, maxCols - 1)

  return (
    <Text>
      {displayed}
      <Text inverse> </Text>
    </Text>
  )
}
