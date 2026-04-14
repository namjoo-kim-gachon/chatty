import React from "react"
import { Box, Text } from "ink"
import type { Message } from "../types.js"
import type { Theme } from "../theme/types.js"
import { useTheme } from "../theme/context.js"

function getNickColorFallback(
  nickname: string,
  nickColors: readonly string[],
): string {
  let sum = 0
  for (let index = 0; index < nickname.length; index++) {
    sum += nickname.codePointAt(index) ?? 0
  }
  return nickColors[sum % nickColors.length] ?? "white"
}

const MS_PER_SECOND = 1000
const NICK_DISPLAY_CHARS = 12

function formatTime(timestamp: number): string {
  const date = new Date(timestamp * MS_PER_SECOND)
  const hh = date.getHours().toString().padStart(2, "0")
  const mm = date.getMinutes().toString().padStart(2, "0")
  return `${hh}:${mm}`
}

function visualWidth(text: string): number {
  let w = 0
  for (const ch of text) {
    w += charWidth(ch.codePointAt(0) ?? 0)
  }
  return w
}

function visualSlice(text: string, maxWidth: number): string {
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

function padToWidth(text: string, width: number): string {
  const pad = width - visualWidth(text)
  return pad > 0 ? text + " ".repeat(pad) : text
}

function getNickPrefix(message: Message, theme: Theme): string {
  switch (message.msg_type) {
    case "system": {
      return padToWidth(theme.symbols.systemPrefix, PREFIX_WIDTH)
    }
    case "game_response": {
      return padToWidth(theme.symbols.gameResponsePrefix, PREFIX_WIDTH)
    }
    case "game_command": {
      return padToWidth(theme.symbols.gameCommandPrefix, PREFIX_WIDTH)
    }
    case "action": {
      return padToWidth(
        visualSlice(
          `${theme.symbols.actionPrefix}${message.nickname}`,
          NICK_DISPLAY_CHARS,
        ),
        PREFIX_WIDTH,
      )
    }
    default: {
      return padToWidth(
        visualSlice(message.nickname, NICK_DISPLAY_CHARS),
        PREFIX_WIDTH,
      )
    }
  }
}

/* eslint-disable no-magic-numbers */
const WIDE_RANGES: readonly (readonly [number, number])[] = [
  [0x11_00, 0x11_5f],
  [0x2e_80, 0x30_3e],
  [0x30_41, 0x33_bf],
  [0x34_00, 0x4d_bf],
  [0x4e_00, 0x9f_ff],
  [0xa0_00, 0xa4_cf],
  [0xac_00, 0xd7_af],
  [0xf9_00, 0xfa_ff],
  [0xfe_10, 0xfe_1f],
  [0xfe_30, 0xfe_4f],
  [0xff_01, 0xff_60],
  [0xff_e0, 0xff_e6],
  [0x1_b0_00, 0x1_b0_ff],
  [0x1_f0_04, 0x1_f0_cf],
  [0x1_f3_00, 0x1_fa_ff],
]
/* eslint-enable no-magic-numbers */

function charWidth(cp: number): number {
  return WIDE_RANGES.some(([start, end]) => cp >= start && cp <= end) ? 2 : 1
}

function wrapText(text: string, maxWidth: number): string[] {
  if (maxWidth <= 0 || text.length === 0) return [""]
  const lines: string[] = []
  let line = ""
  let lineW = 0
  for (const ch of text) {
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

const TIME_WIDTH = 6
const PREFIX_WIDTH = 13

interface MessageRowProps {
  readonly message: Message
  readonly cols: number
  readonly myNickname: string
  readonly nickColorMap: ReadonlyMap<string, number>
}

function MessageRow({
  message,
  cols,
  myNickname,
  nickColorMap,
}: MessageRowProps): React.ReactElement {
  const theme = useTheme()
  const time = formatTime(message.created_at)
  const prefix = getNickPrefix(message, theme)
  const messageType = message.msg_type

  const textWidth = Math.max(1, cols - TIME_WIDTH - PREFIX_WIDTH)
  const lines = wrapText(message.text, textWidth)
  const indent = " ".repeat(TIME_WIDTH + PREFIX_WIDTH)

  const isSelf = myNickname !== "" && message.nickname === myNickname
  const nickColor = (() => {
    if (isSelf) return theme.message.selfNick
    const slot = nickColorMap.get(message.nickname)
    if (slot === undefined) {
      return getNickColorFallback(message.nickname, theme.message.nickColors)
    }
    return (
      theme.message.nickColors[slot % theme.message.nickColors.length] ??
      "white"
    )
  })()

  if (messageType === "chat") {
    return (
      <Box flexDirection="column">
        <Box>
          <Text dimColor>{time} </Text>
          <Text color={nickColor} bold={isSelf}>
            {prefix}
          </Text>
          <Text bold={isSelf}>{lines[0]}</Text>
        </Box>
        {lines.slice(1).map((line, index) => (
          <Box key={index}>
            <Text bold={isSelf}>
              {indent}
              {line}
            </Text>
          </Box>
        ))}
      </Box>
    )
  }

  if (messageType === "system") {
    return (
      <Box flexDirection="column">
        <Box>
          <Text dimColor>{time} </Text>
          <Text color={theme.message.system}>
            {prefix}
            {lines[0]}
          </Text>
        </Box>
        {lines.slice(1).map((line, index) => (
          <Box key={index}>
            <Text color={theme.message.system}>
              {indent}
              {line}
            </Text>
          </Box>
        ))}
      </Box>
    )
  }

  if (messageType === "game_response") {
    return (
      <Box flexDirection="column">
        <Box>
          <Text dimColor>{time} </Text>
          <Text color={theme.message.gameResponse}>
            {prefix}
            {lines[0]}
          </Text>
        </Box>
        {lines.slice(1).map((line, index) => (
          <Box key={index}>
            <Text color={theme.message.gameResponse}>
              {indent}
              {line}
            </Text>
          </Box>
        ))}
      </Box>
    )
  }

  if (messageType === "game_command") {
    return (
      <Box flexDirection="column">
        <Box>
          <Text dimColor>{time} </Text>
          <Text dimColor>
            {prefix}
            {lines[0]}
          </Text>
        </Box>
        {lines.slice(1).map((line, index) => (
          <Box key={index}>
            <Text dimColor>
              {indent}
              {line}
            </Text>
          </Box>
        ))}
      </Box>
    )
  }

  return (
    <Box flexDirection="column">
      <Box>
        <Text dimColor>{time} </Text>
        <Text color={theme.message.action}>
          {prefix}
          {lines[0]}
        </Text>
      </Box>
      {lines.slice(1).map((line, index) => (
        <Box key={index}>
          <Text color={theme.message.action}>
            {indent}
            {line}
          </Text>
        </Box>
      ))}
    </Box>
  )
}

interface MessageListProps {
  readonly messages: Message[]
  readonly visibleRows: number
  readonly scrollOffset: number
  readonly cols: number
  readonly myNickname: string
  readonly nickColorMap: ReadonlyMap<string, number>
}

export function MessageList({
  messages,
  visibleRows,
  scrollOffset,
  cols,
  myNickname,
  nickColorMap,
}: MessageListProps): React.ReactElement {
  const visible = Math.max(1, visibleRows)
  const textWidth = Math.max(1, cols - TIME_WIDTH - PREFIX_WIDTH)

  const lineCounts = messages.map((m) =>
    Math.max(1, wrapText(m.text, textWidth).length),
  )

  let end = messages.length - scrollOffset
  if (end < 0) end = 0
  if (end > messages.length) end = messages.length

  let start = end
  let remaining = visible
  while (start > 0 && remaining > 0) {
    start--
    remaining -= lineCounts[start] ?? 1
  }
  if (remaining < 0 && start < end - 1) {
    start++
  }

  const displayMessages = messages.slice(start, end)

  return (
    <Box flexDirection="column">
      {displayMessages.map((message) => (
        <MessageRow
          key={message.id}
          message={message}
          cols={cols}
          myNickname={myNickname}
          nickColorMap={nickColorMap}
        />
      ))}
    </Box>
  )
}
