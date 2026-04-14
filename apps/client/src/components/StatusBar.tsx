import React from "react"
import { Box, Text } from "ink"
import type { Room, SSEStatus } from "../types.js"
import { useTheme } from "../theme/context.js"
import { useLocale } from "../i18n/context.js"

const ROOM_NUMBER_PAD = 4
const USER_COUNT_PAD = 3
const COLS_COMPACT = 40
const COLS_MEDIUM = 60

interface StatusBarProps {
  readonly room: Room
  readonly userCount: number
  readonly ownerNickname: string
  readonly sseStatus: SSEStatus
  readonly isScrollLocked: boolean
  readonly cols?: number
  readonly showHelp?: boolean
}

function SseDot({
  status,
}: {
  readonly status: SSEStatus
}): React.ReactElement {
  const theme = useTheme()
  const locale = useLocale()
  if (status === "connected")
    return (
      <Text color={theme.status.connected}>
        {theme.symbols.statusDot} {locale.status.connected}
      </Text>
    )
  if (status === "reconnecting")
    return (
      <Text color={theme.status.reconnecting}>
        {theme.symbols.statusDot} {locale.status.reconnecting}
      </Text>
    )
  return (
    <Text color={theme.status.disconnected}>
      {theme.symbols.statusDot} {locale.status.disconnected}
    </Text>
  )
}

export function StatusBar({
  room,
  userCount,
  ownerNickname,
  sseStatus,
  isScrollLocked,
  cols = 80,
  showHelp = false,
}: StatusBarProps): React.ReactElement {
  const theme = useTheme()
  const locale = useLocale()

  if (showHelp) {
    const helpCommands = [
      locale.commands.rooms,
      locale.commands.create,
      `${locale.commands.join} ${locale.commands.joinArg}`,
      locale.commands.who,
      locale.commands.leave,
      `${locale.commands.mute} ${locale.commands.muteArg}`,
      `${locale.commands.unmute} ${locale.commands.unmuteArg}`,
      `${locale.commands.ban} ${locale.commands.banArg}`,
      `${locale.commands.unban} ${locale.commands.unbanArg}`,
      locale.commands.quit,
      "/?",
    ].join(" ")
    return (
      <Box>
        <Text dimColor> {helpCommands}</Text>
      </Box>
    )
  }

  const roomName = room.name
  const roomNumberLabel = `[${room.room_number.toString().padStart(ROOM_NUMBER_PAD, "0")}]`
  const users = `${userCount.toString().padStart(USER_COUNT_PAD, "0")}/${room.max_members.toString().padStart(USER_COUNT_PAD, "0")}`
  const slow =
    room.slow_mode_sec > 0
      ? ` ${theme.symbols.slowModePrefix}${room.slow_mode_sec.toString().padStart(2, "0")}`
      : ""
  const lock = room.is_private ? " *" : ""
  const meta = `${users}${slow}${lock}`
  const ownerHint = ownerNickname.length > 0 ? ` @${ownerNickname}` : ""
  const scrollHint = isScrollLocked ? `  [${locale.status.scrollHint}]` : ""

  if (cols < COLS_COMPACT) {
    return (
      <Box justifyContent="space-between">
        <Box>
          <Text bold>{roomName}</Text>
          <Text> </Text>
          <SseDot status={sseStatus} />
        </Box>
        <Text dimColor>/?</Text>
      </Box>
    )
  }

  if (cols < COLS_MEDIUM) {
    return (
      <Box justifyContent="space-between">
        <Box>
          <Text color={theme.status.roomNumber}>{roomNumberLabel}</Text>
          <Text bold>{` ${roomName}`}</Text>
          <Text dimColor>{` [${meta}]  `}</Text>
          <SseDot status={sseStatus} />
        </Box>
        <Text dimColor>/?</Text>
      </Box>
    )
  }

  return (
    <Box justifyContent="space-between">
      <Box>
        <Text color={theme.status.roomNumber}>{roomNumberLabel}</Text>
        <Text bold>{` ${roomName}`}</Text>
        <Text dimColor>{` [${meta}]`}</Text>
        <Text dimColor>{ownerHint}</Text>
        <Text>{"  "}</Text>
        <SseDot status={sseStatus} />
        {isScrollLocked ? <Text dimColor>{scrollHint}</Text> : undefined}
      </Box>
      <Text dimColor>/?</Text>
    </Box>
  )
}
