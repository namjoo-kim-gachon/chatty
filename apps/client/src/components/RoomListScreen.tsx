import React, { useState, useEffect } from "react"
import { Box, Text, useInput, useCursor } from "ink"
import stringWidth from "string-width"
import { TextInput } from "./TextInput.js"
import { Separator } from "./Separator.js"
import { fetchRooms } from "../lib/client.js"
import { useTheme } from "../theme/context.js"
import { useLocale } from "../i18n/context.js"
import { interpolate } from "../i18n/interpolate.js"
import type { Room, Config, AuthState } from "../types.js"

interface RoomListScreenProps {
  readonly config: Config
  readonly authState: AuthState
  readonly onSelect: (room: Room) => void
  readonly onCancel: () => void
  readonly cols?: number
  readonly rows?: number
}

const HEADER_FOOTER_LINES = 6
const MIN_PAGE_SIZE = 5
const MIN_LIST_WIDTH = 40
const LIST_COL_PADDING = 4
const SEARCH_INPUT_OFFSET = 16
const ROOM_NUMBER_PAD = 4
const USER_COUNT_PAD = 3

export function RoomListScreen({
  config,
  authState,
  onSelect,
  onCancel,
  cols = 80,
  rows = 24,
}: RoomListScreenProps): React.ReactElement {
  const [rooms, setRooms] = useState<Room[]>([])
  const [query, setQuery] = useState("")
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const { setCursorPosition } = useCursor()
  const theme = useTheme()
  const locale = useLocale()

  const pageSize = Math.max(MIN_PAGE_SIZE, rows - HEADER_FOOTER_LINES)
  const totalPages = Math.max(1, Math.ceil(rooms.length / pageSize))
  const currentPage = Math.floor(selectedIndex / pageSize)
  const pageStart = currentPage * pageSize
  const pageEnd = Math.min(pageStart + pageSize, rooms.length)
  const visibleRooms = rooms.slice(pageStart, pageEnd)

  const prefixWidth =
    1 +
    stringWidth(`${locale.roomList.title} `) +
    stringWidth(locale.roomList.search)
  setCursorPosition({
    x: Math.min(prefixWidth + stringWidth(query), cols - 1),
    y: 0,
  })

  useEffect(() => {
    setLoading(true)
    fetchRooms(
      config.server_url,
      authState.token,
      query.length > 0 ? query : undefined,
    )
      .then((result) => {
        setRooms(result)
        setSelectedIndex(0)
        setLoading(false)
      })
      .catch(() => {
        setLoading(false)
      })
  }, [config.server_url, authState.token, query])

  useInput((_input, key) => {
    if (key.escape) {
      onCancel()
      return
    }
    if (key.upArrow) {
      setSelectedIndex((previous) => Math.max(0, previous - 1))
      return
    }
    if (key.downArrow) {
      setSelectedIndex((previous) => Math.min(rooms.length - 1, previous + 1))
      return
    }
    if (key.leftArrow) {
      setSelectedIndex((previous) => {
        const previousPage = Math.floor(previous / pageSize)
        if (previousPage > 0) return (previousPage - 1) * pageSize
        return previous
      })
      return
    }
    if (key.rightArrow) {
      setSelectedIndex((previous) => {
        const previousPage = Math.floor(previous / pageSize)
        if (previousPage < totalPages - 1) return (previousPage + 1) * pageSize
        return previous
      })
      return
    }
    if (key.return && rooms.length > 0) {
      const room = rooms[selectedIndex]
      if (room !== undefined) {
        onSelect(room)
      }
    }
  })

  const listWidth = Math.max(MIN_LIST_WIDTH, cols - LIST_COL_PADDING)

  return (
    <Box flexDirection="column">
      <Box paddingX={1}>
        <Text bold>{locale.roomList.title} </Text>
        <Text dimColor>{locale.roomList.search}</Text>
        <TextInput
          value={query}
          onChange={setQuery}
          // eslint-disable-next-line @typescript-eslint/no-empty-function
          onSubmit={() => {}}
          maxCols={listWidth - SEARCH_INPUT_OFFSET}
        />
      </Box>
      <Separator />
      {loading && (
        <Box paddingX={1}>
          <Text dimColor>{locale.roomList.loading}</Text>
        </Box>
      )}
      {!loading && rooms.length === 0 && (
        <Box paddingX={1}>
          <Text dimColor>{locale.roomList.noRooms}</Text>
        </Box>
      )}
      {!loading &&
        visibleRooms.map((room, index) => {
          const globalIndex = pageStart + index
          const isSelected = globalIndex === selectedIndex
          const roomNumberLabel = `[${room.room_number.toString().padStart(ROOM_NUMBER_PAD, "0")}]`
          const rawName = room.name
          const lock = room.is_private ? "*" : " "
          const nameCol = 18
          let name = rawName
          while (stringWidth(name) > nameCol) {
            name = name.slice(0, -1)
          }
          const namePad = " ".repeat(Math.max(0, nameCol - stringWidth(name)))
          const users = `${room.user_count.toString().padStart(USER_COUNT_PAD, "0")}/${room.max_members.toString().padStart(USER_COUNT_PAD, "0")}`
          const slow =
            room.slow_mode_sec > 0
              ? ` ${theme.symbols.slowModePrefix}${room.slow_mode_sec.toString().padStart(2, "0")}`
              : ""
          const meta = `${users}${slow}`
          return (
            <Box key={room.id} paddingX={1}>
              <Text
                color={isSelected ? theme.ui.selected : "white"}
                bold={isSelected}
              >
                {isSelected ? theme.symbols.selectedRow : "  "}
                <Text color={theme.status.roomNumber}>{roomNumberLabel}</Text>
                {` ${name}${namePad} ${lock}`}
              </Text>
              <Text color="gray">{` [${meta}]`}</Text>
              <Text dimColor>{` ${room.description}`}</Text>
            </Box>
          )
        })}
      <Separator />
      <Box paddingX={1} justifyContent="space-between">
        <Text dimColor>{locale.roomList.help}</Text>
        {!loading && rooms.length > 0 && (
          <Text dimColor>
            {interpolate(locale.roomList.page, {
              current: currentPage + 1,
              total: totalPages,
              count: rooms.length,
            })}
          </Text>
        )}
      </Box>
    </Box>
  )
}
