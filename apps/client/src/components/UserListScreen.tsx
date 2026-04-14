import React, { useState } from "react"
import { Box, Text, useInput } from "ink"
import { Separator } from "./Separator.js"
import { useTheme } from "../theme/context.js"
import { useLocale } from "../i18n/context.js"
import { interpolate } from "../i18n/interpolate.js"
import type { UserEntry } from "../types.js"

const HEADER_FOOTER_LINES = 6
const MIN_PAGE_SIZE = 5

interface UserListScreenProps {
  readonly roomName: string
  readonly users: UserEntry[]
  readonly ownerNickname: string
  readonly myNickname: string
  readonly onClose: () => void
  readonly onMuteToggle?: (userId: string, isMuted: boolean) => void
  readonly onBanUser?: (userId: string) => void
  readonly cols?: number
  readonly rows?: number
}

export function UserListScreen({
  roomName,
  users,
  ownerNickname,
  myNickname,
  onClose,
  onMuteToggle,
  onBanUser,
  rows = 24,
}: UserListScreenProps): React.ReactElement {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const theme = useTheme()
  const locale = useLocale()

  const isOwner = myNickname === ownerNickname
  const pageSize = Math.max(MIN_PAGE_SIZE, rows - HEADER_FOOTER_LINES)
  const totalPages = Math.max(1, Math.ceil(users.length / pageSize))
  const currentPage = Math.floor(selectedIndex / pageSize)
  const pageStart = currentPage * pageSize
  const pageEnd = Math.min(pageStart + pageSize, users.length)
  const visibleUsers = users.slice(pageStart, pageEnd)

  useInput((_input, key) => {
    if (key.escape) {
      onClose()
      return
    }
    if (key.upArrow) {
      setSelectedIndex((previous) => Math.max(0, previous - 1))
      return
    }
    if (key.downArrow) {
      setSelectedIndex((previous) => Math.min(users.length - 1, previous + 1))
      return
    }
    if (key.leftArrow) {
      setSelectedIndex((previous) => {
        const previousPage = Math.floor(previous / pageSize)
        return previousPage > 0 ? (previousPage - 1) * pageSize : previous
      })
      return
    }
    if (key.rightArrow) {
      setSelectedIndex((previous) => {
        const previousPage = Math.floor(previous / pageSize)
        return previousPage < totalPages - 1
          ? (previousPage + 1) * pageSize
          : previous
      })
      return
    }
    if (_input === "m" && isOwner && onMuteToggle !== undefined) {
      const selectedUser = users[selectedIndex]
      if (
        selectedUser !== undefined &&
        selectedUser.nickname !== ownerNickname
      ) {
        onMuteToggle(selectedUser.id, selectedUser.isMuted)
      }
    }
    if (_input === "b" && isOwner && onBanUser !== undefined) {
      const selectedUser = users[selectedIndex]
      if (
        selectedUser !== undefined &&
        selectedUser.nickname !== ownerNickname
      ) {
        onBanUser(selectedUser.id)
      }
    }
  })

  const helpText = isOwner ? locale.userList.helpOwner : locale.userList.help

  return (
    <Box flexDirection="column">
      <Separator />
      <Box paddingX={1}>
        <Text bold>
          {interpolate(locale.userList.onlineCount, {
            name: roomName,
            count: users.length,
          })}
        </Text>
      </Box>
      <Separator />
      {users.length === 0 ? (
        <Box paddingX={1}>
          <Text dimColor>{locale.userList.noUsers}</Text>
        </Box>
      ) : (
        visibleUsers.map((user, index) => {
          const globalIndex = pageStart + index
          const isSelected = globalIndex === selectedIndex
          const isRowOwner = user.nickname === ownerNickname
          let rowPrefix = "  "
          if (isSelected) rowPrefix = theme.symbols.selectedRow
          else if (isRowOwner) rowPrefix = theme.symbols.ownerRow

          let nameColor = theme.ui.defaultText
          if (isRowOwner) nameColor = theme.ui.ownerName
          else if (user.isMuted) nameColor = theme.ui.mutedName

          let suffix = ""
          if (isRowOwner) suffix = ` ${locale.userList.owner}`
          else if (user.isMuted) suffix = ` ${locale.userList.muted}`

          return (
            <Box key={user.id} paddingX={1}>
              <Text color={nameColor} bold={isSelected}>
                {rowPrefix}
                {user.nickname}
                {suffix}
              </Text>
            </Box>
          )
        })
      )}
      <Separator />
      <Box paddingX={1} justifyContent="space-between">
        <Text dimColor>{helpText}</Text>
        {users.length > 0 && (
          <Text dimColor>
            {interpolate(locale.userList.page, {
              current: currentPage + 1,
              total: totalPages,
              count: users.length,
            })}
          </Text>
        )}
      </Box>
    </Box>
  )
}
