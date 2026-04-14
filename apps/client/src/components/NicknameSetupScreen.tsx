import React, { useState } from "react"
import { Box, Text, useApp, useInput } from "ink"

import { useLocale } from "../i18n/context.js"
import { ApiError, setNickname } from "../lib/auth.js"
import type { Config } from "../types.js"
import { TextInput } from "./TextInput.js"

interface Props {
  readonly config: Config
  readonly token: string
  readonly suggestedNickname: string
  readonly onComplete: (nickname: string, isAdmin: boolean) => void
  readonly title?: string | undefined
  readonly subtitle?: string | undefined
  readonly forbidSame?: boolean | undefined
}

const HTTP_CONFLICT = 409

type Step = "idle" | "loading" | "error"

export function NicknameSetupScreen({
  config,
  token,
  suggestedNickname,
  onComplete,
  title,
  subtitle,
  forbidSame,
}: Props): React.ReactElement {
  const { exit } = useApp()
  const locale = useLocale()
  const [nickname, setNicknameValue] = useState(suggestedNickname)
  const [step, setStep] = useState<Step>("idle")
  const [error, setError] = useState("")

  useInput((input, key) => {
    if (key.ctrl && input === "c") exit()
  })

  const handleSubmit = (value: string): void => {
    const trimmed = value.trim()
    if (trimmed.length < 2) return
    if (forbidSame === true && trimmed === suggestedNickname) {
      setError(locale.login.nicknameSame)
      setStep("error")
      return
    }
    setStep("loading")
    setNickname(config.server_url, token, trimmed)
      .then((user) => {
        onComplete(user.nickname, user.is_admin)
      })
      .catch((error_: unknown) => {
        if (error_ instanceof ApiError && error_.status === HTTP_CONFLICT) {
          setError(locale.login.nicknameTaken)
        } else {
          setError(error_ instanceof Error ? error_.message : "Unknown error")
        }
        setStep("error")
      })
  }

  return (
    <Box flexDirection="column" gap={1}>
      <Text bold>{title ?? locale.login.nicknameSetupTitle}</Text>
      <Text dimColor>{subtitle ?? locale.login.nicknameSetupSubtitle}</Text>
      <Box>
        <Text dimColor>{locale.login.nicknameSetupLabel}</Text>
        {step === "loading" ? (
          <Text>{locale.login.nicknameSetupSetting}</Text>
        ) : (
          <TextInput
            value={nickname}
            onChange={setNicknameValue}
            onSubmit={handleSubmit}
          />
        )}
      </Box>
      {step === "error" ? <Text color="red">{error}</Text> : undefined}
    </Box>
  )
}
