import React, { useState } from "react"
import { Box, Text, useInput } from "ink"
import { TextInput } from "./TextInput.js"
import { Separator } from "./Separator.js"
import { createRoom } from "../lib/client.js"
import { useTheme } from "../theme/context.js"
import { useLocale } from "../i18n/context.js"
import type { Config, AuthState, Room } from "../types.js"

interface CreateRoomFormProps {
  readonly config: Config
  readonly authState: AuthState
  readonly onCreated: (room: Room) => void
  readonly onCancel: () => void
}

// eslint-disable-next-line no-magic-numbers
type FieldIndex = 0 | 1 | 2 | 3 | 4

const FIELD_COUNT = 5
const MAX_MEMBERS_DEFAULT = 500
const MAX_MEMBERS_LIMIT = 500
const MAX_SLOW_MODE_SEC = 99
const FIELD_INDEX_NAME = 0
const FIELD_INDEX_MAX_MEMBERS = 3
const FIELD_INDEX_SLOW_MODE = 4
const LABEL_PAD_WIDTH = 8

export function CreateRoomForm({
  config,
  authState,
  onCreated,
  onCancel,
}: CreateRoomFormProps): React.ReactElement {
  const [focusIndex, setFocusIndex] = useState<FieldIndex>(0)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [password, setPassword] = useState("")
  const [maxMembers, setMaxMembers] = useState(String(MAX_MEMBERS_DEFAULT))
  const [slowMode, setSlowMode] = useState("1")
  const [error, setError] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const theme = useTheme()
  const locale = useLocale()

  useInput((_input, key) => {
    if (key.escape) {
      onCancel()
      return
    }
    if (key.tab && !key.shift) {
      setFocusIndex(((focusIndex + 1) % FIELD_COUNT) as FieldIndex)
      return
    }
    if (key.shift && key.tab) {
      setFocusIndex(
        ((focusIndex - 1 + FIELD_COUNT) % FIELD_COUNT) as FieldIndex,
      )
      return
    }
    if (key.return && focusIndex !== 0) {
      void handleSubmit()
    }
  })

  const handleSubmit = async (): Promise<void> => {
    if (name.trim().length === 0) {
      setError(locale.createRoom.errorNameRequired)
      setFocusIndex(FIELD_INDEX_NAME)
      return
    }
    const parsedMax =
      maxMembers.length > 0
        ? Number.parseInt(maxMembers, 10)
        : MAX_MEMBERS_DEFAULT
    if (parsedMax < 2 || parsedMax > MAX_MEMBERS_LIMIT) {
      setError(locale.createRoom.errorMaxRange)
      setFocusIndex(FIELD_INDEX_MAX_MEMBERS)
      return
    }
    const parsedSlow = slowMode.length > 0 ? Number.parseInt(slowMode, 10) : 1
    if (parsedSlow < 0 || parsedSlow > MAX_SLOW_MODE_SEC) {
      setError(locale.createRoom.errorSlowRange)
      setFocusIndex(FIELD_INDEX_SLOW_MODE)
      return
    }
    setSubmitting(true)
    setError("")
    try {
      const options = {
        name: name.trim(),
        max_members: parsedMax,
        slow_mode_sec: parsedSlow,
        ...(description.trim().length > 0
          ? { description: description.trim() }
          : {}),
        ...(password.trim().length > 0 ? { password: password.trim() } : {}),
      }
      const room = await createRoom(config.server_url, authState.token, options)
      onCreated(room)
    } catch (error_: unknown) {
      setError(
        error_ instanceof Error
          ? error_.message
          : locale.createRoom.errorCreateFailed,
      )
      setSubmitting(false)
    }
  }

  const renderField = (
    label: string,
    index: FieldIndex,
    value: string,
    onChange: (v: string) => void,
    isMasked: boolean,
  ): React.ReactElement => {
    const isFocused = focusIndex === index
    const maskedDisplay = "*".repeat(value.length)
    const plainDisplay = value.length > 0 ? value : " "
    const displayText = isMasked ? maskedDisplay : plainDisplay
    const maskProperty = isMasked ? { mask: "*" as const } : {}
    return (
      <Box>
        <Text color={isFocused ? theme.ui.focusedField : "white"}>
          {`  ${label.padEnd(LABEL_PAD_WIDTH)}: `}
        </Text>
        {isFocused ? (
          <TextInput
            value={value}
            onChange={onChange}
            onSubmit={() => {
              void handleSubmit()
            }}
            {...maskProperty}
          />
        ) : (
          <Text dimColor>{displayText}</Text>
        )}
      </Box>
    )
  }

  return (
    <Box flexDirection="column">
      <Box paddingX={1}>
        <Text bold>{locale.createRoom.title}</Text>
      </Box>
      <Separator />
      {renderField(locale.createRoom.fieldName, 0, name, setName, false)}
      {renderField(
        locale.createRoom.fieldDescription,
        1,
        description,
        setDescription,
        false,
      )}
      {renderField(
        locale.createRoom.fieldPassword,
        2,
        password,
        setPassword,
        true,
      )}
      {renderField(
        locale.createRoom.fieldMaxMembers,
        FIELD_INDEX_MAX_MEMBERS,
        maxMembers,
        setMaxMembers,
        false,
      )}
      {renderField(
        locale.createRoom.fieldSlowMode,
        FIELD_INDEX_SLOW_MODE,
        slowMode,
        setSlowMode,
        false,
      )}
      {error.length > 0 ? (
        <Box paddingX={1}>
          <Text color="red">{error}</Text>
        </Box>
      ) : undefined}
      <Separator />
      <Box paddingX={1}>
        {submitting ? (
          <Text dimColor>{locale.createRoom.creating}</Text>
        ) : (
          <Text dimColor>{locale.createRoom.help}</Text>
        )}
      </Box>
    </Box>
  )
}
