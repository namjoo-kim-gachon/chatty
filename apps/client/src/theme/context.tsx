import React, { createContext, useContext } from "react"
import type { Theme } from "./types.js"
import { defaultTheme } from "./default.js"

const ThemeContext = createContext(defaultTheme)

interface ThemeProviderProps {
  readonly theme: Theme
  readonly children: React.ReactNode
}

export function ThemeProvider({
  theme,
  children,
}: ThemeProviderProps): React.ReactElement {
  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>
}

export function useTheme(): Theme {
  return useContext(ThemeContext)
}
