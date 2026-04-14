import React from "react"
import { Text, useStdout } from "ink"
import { useTheme } from "../theme/context.js"

const DEFAULT_COLS = 80

export function Separator(): React.ReactElement {
  const { stdout } = useStdout()
  const theme = useTheme()
  const cols = stdout.columns > 0 ? stdout.columns : DEFAULT_COLS
  return <Text dimColor>{theme.symbols.separator.repeat(cols)}</Text>
}
