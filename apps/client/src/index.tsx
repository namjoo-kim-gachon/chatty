#!/usr/bin/env node
import React, { useCallback, useEffect, useState } from "react"
import { Box, Text, render, useApp, useInput } from "ink"

import { App } from "./app.js"
import { loadConfig } from "./config.js"
import { LocaleProvider, useLocale } from "./i18n/context.js"
import { loadLocale } from "./i18n/loader.js"
import { interpolate } from "./i18n/interpolate.js"
import {
  buildAuthState,
  pollOAuth,
  refreshToken,
  startOAuth,
} from "./lib/auth.js"
import {
  clearTokens,
  getIsAdminFromToken,
  getNicknameFromToken,
  isAccessTokenExpired,
  readTokens,
  writeTokens,
} from "./lib/tokenStore.js"
import { startSocketServer } from "./socket/server.js"
import { loadTheme } from "./theme/loader.js"
import { ThemeProvider } from "./theme/context.js"
import { NicknameSetupScreen } from "./components/NicknameSetupScreen.js"
import type { AuthState, Config } from "./types.js"

const POLL_INTERVAL_MS = 2000
const MAX_POLL_ATTEMPTS = 150 // 5 minutes
const LOGIN_DONE_DISPLAY_MS = 1500

// ---------------------------------------------------------------------------
// TUI login screen (shared by both CLI login and TUI mode)
// ---------------------------------------------------------------------------

type LoginStep =
  | { kind: "starting" }
  | { kind: "waiting"; url: string; state: string }
  | { kind: "error"; message: string }

interface GoogleLoginScreenProps {
  readonly config: Config
  readonly onLogin: (
    authState: AuthState,
    isNewUser: boolean,
    suggested: string,
  ) => void
}

function GoogleLoginScreen({
  config,
  onLogin,
}: GoogleLoginScreenProps): React.ReactElement {
  const { exit } = useApp()
  const locale = useLocale()
  const [step, setStep] = useState<LoginStep>({ kind: "starting" })

  useInput((input, key) => {
    if (key.ctrl && input === "c") exit()
  })

  useEffect(() => {
    startOAuth(config.server_url)
      .then(({ url, state }) => {
        setStep({ kind: "waiting", url, state })
      })
      .catch((error: unknown) => {
        const message =
          error instanceof Error ? error.message : locale.login.oauthFailed
        setStep({ kind: "error", message })
      })
  }, [config.server_url, locale.login.oauthFailed])

  useEffect(() => {
    if (step.kind !== "waiting") return
    const { state } = step
    let attempts = 0
    const interval = setInterval(() => {
      attempts++
      if (attempts > MAX_POLL_ATTEMPTS) {
        clearInterval(interval)
        setStep({ kind: "error", message: locale.login.oauthTimedOut })
        return
      }
      pollOAuth(config.server_url, state)
        .then((result) => {
          if (result.status === "error") {
            clearInterval(interval)
            setStep({
              kind: "error",
              message: result.error ?? locale.login.oauthFailed,
            })
            return
          }
          if (
            result.status === "complete" &&
            result.access_token !== undefined &&
            result.refresh_token !== undefined &&
            result.user !== undefined
          ) {
            clearInterval(interval)
            const authState = buildAuthState(
              result.user,
              result.access_token,
              result.refresh_token,
            )
            writeTokens(authState)
            onLogin(
              authState,
              result.is_new_user === true,
              result.suggested_nickname ?? result.user.nickname,
            )
          }
        })
        .catch(() => {
          // network error — keep polling
        })
    }, POLL_INTERVAL_MS)
    return () => {
      clearInterval(interval)
    }
  }, [
    step,
    config.server_url,
    onLogin,
    locale.login.oauthTimedOut,
    locale.login.oauthFailed,
  ])

  if (step.kind === "starting") {
    return (
      <Box>
        <Text dimColor>{locale.login.oauthConnecting}</Text>
      </Box>
    )
  }

  if (step.kind === "error") {
    return (
      <Box flexDirection="column">
        <Text color="red">{step.message}</Text>
      </Box>
    )
  }

  return (
    <Box flexDirection="column" gap={1}>
      <Text bold>{locale.login.oauthTitle}</Text>
      <Text>{locale.login.oauthOpenUrl}</Text>
      <Text color="cyan">{step.url}</Text>
      <Text dimColor>{locale.login.oauthWaiting}</Text>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// CLI login command screen (chatty login)
// ---------------------------------------------------------------------------

interface LoginCommandScreenProps {
  readonly config: Config
}

function LoginCommandScreen({
  config,
}: LoginCommandScreenProps): React.ReactElement {
  const { exit } = useApp()
  const locale = useLocale()
  const [done, setDone] = useState<{
    nickname: string
    isNew: boolean
  } | null>(null)

  useEffect(() => {
    if (done === null) return
    const timer = setTimeout(() => {
      exit()
    }, LOGIN_DONE_DISPLAY_MS)
    return () => {
      clearTimeout(timer)
    }
  }, [done, exit])

  const handleLogin = useCallback(
    (authState: AuthState, isNewUser: boolean, _suggested: string) => {
      if (isNewUser) {
        writeTokens({ ...authState, needs_nickname: true })
      }
      setDone({ nickname: authState.nickname, isNew: isNewUser })
    },
    [],
  )

  if (done !== null) {
    return (
      <Box flexDirection="column" gap={1}>
        <Text color="green">
          {interpolate(locale.login.loggedInAs, { nick: done.nickname })}
        </Text>
        {done.isNew && <Text dimColor>{locale.login.newUserHint}</Text>}
      </Box>
    )
  }

  return <GoogleLoginScreen config={config} onLogin={handleLogin} />
}

// ---------------------------------------------------------------------------
// Root TUI component
// ---------------------------------------------------------------------------

type RootStep =
  | { kind: "loading" }
  | { kind: "login" }
  | {
      kind: "nickname"
      authState: AuthState
      suggested: string
    }
  | { kind: "app"; authState: AuthState }

interface RootProps {
  readonly config: Config
}

function Root({ config }: RootProps): React.ReactElement {
  const { exit } = useApp()
  const [step, setStep] = useState<RootStep>({ kind: "loading" })

  useInput((_input, key) => {
    if (key.ctrl && _input === "c") exit()
  })

  useEffect(() => {
    const saved = readTokens()
    if (saved === null) {
      setStep({ kind: "login" })
      return
    }

    if (!isAccessTokenExpired(saved.token)) {
      if (saved.needs_nickname === true) {
        setStep({
          kind: "nickname",
          authState: saved,
          suggested: getNicknameFromToken(saved.token),
        })
      } else {
        setStep({ kind: "app", authState: saved })
      }
      return
    }

    // Access token expired — try refresh
    refreshToken(config.server_url, saved.refresh_token)
      .then((tokens) => {
        if (tokens === null) {
          clearTokens()
          setStep({ kind: "login" })
          return
        }
        const renewed: AuthState = {
          ...saved,
          token: tokens.access_token,
          refresh_token: tokens.refresh_token,
          nickname: getNicknameFromToken(tokens.access_token),
          is_admin: getIsAdminFromToken(tokens.access_token),
        }
        writeTokens(renewed)
        setStep({ kind: "app", authState: renewed })
      })
      .catch(() => {
        clearTokens()
        setStep({ kind: "login" })
      })
  }, [config.server_url])

  const handleLogin = useCallback(
    (authState: AuthState, isNewUser: boolean, suggested: string) => {
      if (isNewUser) {
        writeTokens({ ...authState, needs_nickname: true })
        setStep({
          kind: "nickname",
          authState: { ...authState, needs_nickname: true },
          suggested,
        })
      } else {
        setStep({ kind: "app", authState })
      }
    },
    [],
  )

  const handleNicknameComplete = useCallback(
    (_nickname: string, _isAdmin: boolean) => {
      if (step.kind !== "nickname") return
      refreshToken(config.server_url, step.authState.refresh_token)
        .then((tokens) => {
          if (tokens === null) {
            clearTokens()
            setStep({ kind: "login" })
            return
          }
          const renewed: AuthState = {
            token: tokens.access_token,
            refresh_token: tokens.refresh_token,
            user_id: step.authState.user_id,
            nickname: getNicknameFromToken(tokens.access_token),
            is_admin: getIsAdminFromToken(tokens.access_token),
            needs_nickname: false,
          }
          writeTokens(renewed)
          setStep({ kind: "app", authState: renewed })
        })
        .catch(() => {
          clearTokens()
          setStep({ kind: "login" })
        })
    },
    [step, config.server_url],
  )

  const handleLogout = useCallback(() => {
    clearTokens()
    setStep({ kind: "login" })
  }, [])

  if (step.kind === "loading") {
    return (
      <Box>
        <Text dimColor>Loading...</Text>
      </Box>
    )
  }

  if (step.kind === "login") {
    return <GoogleLoginScreen config={config} onLogin={handleLogin} />
  }

  if (step.kind === "nickname") {
    return (
      <NicknameSetupScreen
        config={config}
        token={step.authState.token}
        suggestedNickname={step.suggested}
        onComplete={handleNicknameComplete}
      />
    )
  }

  return (
    <App config={config} authState={step.authState} onLogout={handleLogout} />
  )
}

// ---------------------------------------------------------------------------
// Nickname change command screen (chatty nickname)
// ---------------------------------------------------------------------------

interface NicknameCommandScreenProps {
  readonly config: Config
  readonly authState: AuthState
}

function NicknameCommandScreen({
  config,
  authState,
}: NicknameCommandScreenProps): React.ReactElement {
  const { exit } = useApp()
  const locale = useLocale()
  const [done, setDone] = useState<string | null>(null)

  useEffect(() => {
    if (done === null) return
    const timer = setTimeout(() => {
      exit()
    }, LOGIN_DONE_DISPLAY_MS)
    return () => {
      clearTimeout(timer)
    }
  }, [done, exit])

  const handleComplete = useCallback(
    (_nickname: string, _isAdmin: boolean) => {
      refreshToken(config.server_url, authState.refresh_token)
        .then((tokens) => {
          if (tokens === null) {
            exit()
            return
          }
          const renewed: AuthState = {
            token: tokens.access_token,
            refresh_token: tokens.refresh_token,
            user_id: authState.user_id,
            nickname: getNicknameFromToken(tokens.access_token),
            is_admin: getIsAdminFromToken(tokens.access_token),
          }
          writeTokens(renewed)
          setDone(renewed.nickname)
        })
        .catch(() => {
          exit()
        })
    },
    [config.server_url, authState, exit],
  )

  if (done !== null) {
    return (
      <Box>
        <Text color="green">
          {interpolate(locale.login.nicknameCmdChanged, { nick: done })}
        </Text>
      </Box>
    )
  }

  return (
    <NicknameSetupScreen
      config={config}
      token={authState.token}
      suggestedNickname={authState.nickname}
      title={locale.login.nicknameChangeTitle}
      subtitle={locale.login.nicknameChangeSubtitle}
      forbidSame
      onComplete={handleComplete}
    />
  )
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

const config = loadConfig()
const theme = loadTheme(config.theme)
const locale = loadLocale(config.locale)

if (process.argv[2] === "nickname") {
  const saved = readTokens()
  if (saved === null) {
    process.stderr.write(locale.login.nicknameCmdNotLoggedIn + "\n")
    process.exit(1)
  }

  let authState = saved
  if (isAccessTokenExpired(saved.token)) {
    const tokens = await refreshToken(config.server_url, saved.refresh_token)
    if (tokens === null) {
      clearTokens()
      process.stderr.write(locale.login.nicknameCmdNotLoggedIn + "\n")
      process.exit(1)
    }
    authState = {
      ...saved,
      token: tokens.access_token,
      refresh_token: tokens.refresh_token,
      nickname: getNicknameFromToken(tokens.access_token),
      is_admin: getIsAdminFromToken(tokens.access_token),
    }
  }

  const { waitUntilExit } = render(
    <ThemeProvider theme={theme}>
      <LocaleProvider locale={locale}>
        <NicknameCommandScreen config={config} authState={authState} />
      </LocaleProvider>
    </ThemeProvider>,
    { exitOnCtrlC: false },
  )

  process.on("SIGINT", () => {
    process.exit(0)
  })

  await waitUntilExit()
  process.exit(0)
} else if (process.argv[2] === "login") {
  const { waitUntilExit } = render(
    <ThemeProvider theme={theme}>
      <LocaleProvider locale={locale}>
        <LoginCommandScreen config={config} />
      </LocaleProvider>
    </ThemeProvider>,
    { exitOnCtrlC: false },
  )

  process.on("SIGINT", () => {
    process.exit(0)
  })

  await waitUntilExit()
  process.exit(0)
} else {
  const { waitUntilExit } = render(
    <ThemeProvider theme={theme}>
      <LocaleProvider locale={locale}>
        <Root config={config} />
      </LocaleProvider>
    </ThemeProvider>,
    { exitOnCtrlC: false },
  )

  startSocketServer()

  process.on("SIGINT", () => {
    process.exit(0)
  })

  await waitUntilExit()
  process.exit(0)
}
