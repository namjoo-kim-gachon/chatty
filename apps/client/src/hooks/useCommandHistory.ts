import { useState, useCallback } from "react"

interface UseCommandHistoryResult {
  historyUp: (current: string) => string
  historyDown: () => string
  goToBottom: () => string
  addToHistory: (command: string) => void
  reset: () => void
}

export function useCommandHistory(): UseCommandHistoryResult {
  const [history, setHistory] = useState<string[]>([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [savedInput, setSavedInput] = useState("")

  const MAX_HISTORY = 20

  const addToHistory = useCallback((command: string) => {
    const trimmed = command.trim()
    if (!trimmed) return
    setHistory((previous) => {
      if (previous.at(-1) === trimmed) return previous
      const next = [...previous, trimmed]
      return next.length > MAX_HISTORY ? next.slice(-MAX_HISTORY) : next
    })
    setHistoryIndex(-1)
    setSavedInput("")
  }, [])

  const historyUp = useCallback(
    (current: string) => {
      if (history.length === 0) return current

      let newIndex: number
      if (historyIndex === -1) {
        setSavedInput(current)
        newIndex = history.length - 1
      } else {
        newIndex = Math.max(0, historyIndex - 1)
      }
      setHistoryIndex(newIndex)
      return history[newIndex] ?? current
    },
    [history, historyIndex],
  )

  const historyDown = useCallback(() => {
    if (historyIndex === -1) return ""

    const newIndex = historyIndex + 1
    if (newIndex >= history.length) {
      setHistoryIndex(-1)
      return savedInput
    }
    setHistoryIndex(newIndex)
    return history[newIndex] ?? ""
  }, [history, historyIndex, savedInput])

  const goToBottom = useCallback(() => {
    const saved = savedInput
    setHistoryIndex(-1)
    setSavedInput("")
    return saved
  }, [savedInput])

  const reset = useCallback(() => {
    setHistoryIndex(-1)
    setSavedInput("")
  }, [])

  return { historyUp, historyDown, goToBottom, addToHistory, reset }
}
