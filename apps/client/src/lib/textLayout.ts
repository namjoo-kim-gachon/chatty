import { eastAsianWidth } from "get-east-asian-width"
import type { Message } from "../types.js"

export function charWidth(cp: number): number {
  return eastAsianWidth(cp, { ambiguousAsWide: true })
}

export function visualWidth(text: string): number {
  let w = 0
  for (const ch of text) {
    w += charWidth(ch.codePointAt(0) ?? 0)
  }
  return w
}

export function visualSlice(text: string, maxWidth: number): string {
  let w = 0
  let result = ""
  for (const ch of text) {
    const cw = charWidth(ch.codePointAt(0) ?? 0)
    if (w + cw > maxWidth) break
    result += ch
    w += cw
  }
  return result
}

export function padToWidth(text: string, width: number): string {
  const pad = width - visualWidth(text)
  return pad > 0 ? text + " ".repeat(pad) : text
}

export function wrapText(text: string, maxWidth: number): string[] {
  if (maxWidth <= 0 || text.length === 0) return [""]
  const lines: string[] = []
  let line = ""
  let lineW = 0
  for (const ch of text) {
    if (ch === "\n") {
      lines.push(line)
      line = ""
      lineW = 0
      continue
    }
    const cw = charWidth(ch.codePointAt(0) ?? 0)
    if (lineW + cw > maxWidth) {
      lines.push(line)
      line = ch
      lineW = cw
    } else {
      line += ch
      lineW += cw
    }
  }
  lines.push(line)
  return lines
}

export const TIME_WIDTH = 6
export const PREFIX_WIDTH = 13

export function computeTotalLines(messages: Message[], cols: number): number {
  const textWidth = Math.max(1, cols - TIME_WIDTH - PREFIX_WIDTH)
  return messages.reduce(
    (sum, m) => sum + Math.max(1, wrapText(m.text, textWidth).length),
    0,
  )
}
