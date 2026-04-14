import React, { createContext, useContext } from "react"
import type { Locale } from "./types.js"
import { defaultLocale } from "./default.js"

const LocaleContext = createContext<Locale>(defaultLocale)

interface LocaleProviderProps {
  readonly locale: Locale
  readonly children: React.ReactNode
}

export function LocaleProvider({
  locale,
  children,
}: LocaleProviderProps): React.ReactElement {
  return (
    <LocaleContext.Provider value={locale}>{children}</LocaleContext.Provider>
  )
}

export function useLocale(): Locale {
  return useContext(LocaleContext)
}
