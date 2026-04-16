import React, { useState, useCallback } from "react"
import { Box, Text, useInput, useCursor, useStdout } from "ink"
import stringWidth from "string-width"
import { TextInput } from "./TextInput.js"
import { useCommandHistory } from "../hooks/useCommandHistory.js"
import { useTheme } from "../theme/context.js"
import type { RoomType } from "../types.js"

interface InputBarProps {
  readonly roomType: RoomType
  readonly nickname: string
  readonly onSubmit: (text: string) => void
  readonly cols?: number
}

export function InputBar({
  roomType,
  nickname,
  onSubmit,
  cols = 80,
}: InputBarProps): React.ReactElement {
  const [inputValue, setInputValue] = useState("")
  const { historyUp, historyDown, goToBottom, addToHistory, reset } =
    useCommandHistory()
  const { setCursorPosition } = useCursor()
  const { stdout } = useStdout()
  const theme = useTheme()
  const isGame = roomType === "game"
  useInput((_input, key) => {
    if (key.upArrow) {
      setInputValue(historyUp(inputValue))
      return
    }
    if (key.downArrow) {
      setInputValue(historyDown())
      return
    }
    if (key.escape) {
      setInputValue(goToBottom())
      return
    }
    // Let other keys (PageUp, PageDown, Home, End, etc.) bubble up
  })

  const handleSubmit = useCallback(
    (text: string) => {
      const trimmed = text.trim()
      if (!trimmed) return
      addToHistory(trimmed)
      reset()
      setInputValue("")
      onSubmit(trimmed)
    },
    [addToHistory, reset, onSubmit],
  )

  const fullPrompt = `${nickname} > `
  const useColoredPrompt = !isGame && fullPrompt.length < cols
  const promptWidth = useColoredPrompt
    ? stringWidth(fullPrompt)
    : stringWidth("> ")
  const inputMaxCols = Math.max(1, cols - promptWidth)

  setCursorPosition({
    x: Math.min(promptWidth + stringWidth(inputValue), cols - 1),
    y: stdout.rows - 2,
  })

  return (
    <Box>
      {useColoredPrompt ? (
        <>
          <Text color={theme.message.selfNick} bold>
            {nickname}
          </Text>
          <Text>{" >"} </Text>
        </>
      ) : (
        <Text dimColor>{"> "}</Text>
      )}
      <TextInput
        value={inputValue}
        onChange={setInputValue}
        onSubmit={handleSubmit}
        maxCols={inputMaxCols}
      />
    </Box>
  )
}
