import React, { useState } from "react"
import { Box, Text, useInput } from "ink"
import { TextInput } from "./TextInput.js"
import { Separator } from "./Separator.js"
import { useLocale } from "../i18n/context.js"
import { interpolate } from "../i18n/interpolate.js"

interface PasswordInputScreenProps {
  readonly roomName: string
  readonly onSubmit: (password: string) => void
  readonly onCancel: () => void
  readonly error?: string
}

export function PasswordInputScreen({
  roomName,
  onSubmit,
  onCancel,
  error,
}: PasswordInputScreenProps): React.ReactElement {
  const [password, setPassword] = useState("")
  const locale = useLocale()

  useInput((_input, key) => {
    if (key.escape) {
      onCancel()
    }
  })

  return (
    <Box flexDirection="column">
      <Separator />
      <Box paddingX={1}>
        <Text bold>
          {interpolate(locale.passwordInput.title, { name: roomName })}
        </Text>
      </Box>
      <Separator />
      <Box paddingX={1}>
        <Text dimColor>{locale.passwordInput.label}</Text>
        <TextInput
          value={password}
          onChange={setPassword}
          onSubmit={onSubmit}
          mask="*"
        />
      </Box>
      {error !== undefined && error.length > 0 ? (
        <Box paddingX={1}>
          <Text color="red">{error}</Text>
        </Box>
      ) : undefined}
      <Separator />
      <Box paddingX={1}>
        <Text dimColor>{locale.passwordInput.help}</Text>
      </Box>
    </Box>
  )
}
