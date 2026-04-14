import { useState, useCallback } from "react"

interface UseScrollResult {
  scrollOffset: number
  isScrollLocked: boolean
  lockScroll: () => void
  unlockScroll: () => void
  scrollUp: (amount?: number) => void
  scrollDown: (amount?: number) => void
}

export function useScroll(messageCount: number): UseScrollResult {
  const [scrollOffset, setScrollOffset] = useState(0)
  const [isScrollLocked, setIsScrollLocked] = useState(false)

  const lockScroll = useCallback(() => {
    setIsScrollLocked(true)
  }, [])

  const unlockScroll = useCallback(() => {
    setIsScrollLocked(false)
    setScrollOffset(0)
  }, [])

  const scrollUp = useCallback(
    (amount = 3) => {
      setIsScrollLocked(true)
      setScrollOffset((previous) =>
        Math.min(previous + amount, Math.max(0, messageCount - 1)),
      )
    },
    [messageCount],
  )

  const scrollDown = useCallback((amount = 3) => {
    setScrollOffset((previous) => {
      const next = Math.max(0, previous - amount)
      if (next === 0) {
        setIsScrollLocked(false)
      }
      return next
    })
  }, [])

  return {
    scrollOffset,
    isScrollLocked,
    lockScroll,
    unlockScroll,
    scrollUp,
    scrollDown,
  }
}
