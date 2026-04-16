import { useState, useCallback } from "react"
import type { useStdout } from "ink"

interface UseScrollResult {
  scrollOffset: number
  isScrollLocked: boolean
  lockScroll: () => void
  unlockScroll: () => void
  scrollUp: (amount?: number) => void
  scrollDown: (amount?: number) => void
  scrollToTop: () => void
}

export function useScroll(
  totalLines: number,
  visibleRows: number,
  _stdout: ReturnType<typeof useStdout>["stdout"],
): UseScrollResult {
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
      // scrollOffset is in LINE units. maxOffset = lines above the current view.
      const maxOffset = Math.max(0, totalLines - visibleRows)
      if (maxOffset === 0) return // nothing to scroll up
      setScrollOffset((previous) => Math.min(previous + amount, maxOffset))
      setIsScrollLocked(true)
    },
    [totalLines, visibleRows],
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

  const scrollToTop = useCallback(() => {
    const maxOffset = Math.max(0, totalLines - visibleRows)
    setIsScrollLocked(maxOffset > 0)
    setScrollOffset(maxOffset)
  }, [totalLines, visibleRows])

  return {
    scrollOffset,
    isScrollLocked,
    lockScroll,
    unlockScroll,
    scrollUp,
    scrollDown,
    scrollToTop,
  }
}
