import type { Theme } from "./types.js"

const COLORS = {
  cyan: "#8be9fd",
  green: "#50fa7b",
  pink: "#ff79c6",
  purple: "#bd93f9",
  red: "#ff5555",
  yellow: "#f1fa8c",
  orange: "#ffb86c",
  white: "#f8f8f2",
  brightCyan: "#6be5fd",
  brightGreen: "#69ff94",
  brightPink: "#ff92df",
  brightPurple: "#d6acff",
} as const

const NICK_COLORS = [
  COLORS.cyan,
  COLORS.green,
  COLORS.pink,
  COLORS.purple,
  COLORS.red,
  COLORS.orange,
  COLORS.brightCyan,
  COLORS.brightGreen,
  COLORS.brightPink,
  COLORS.brightPurple,
] as const

export const draculaTheme: Theme = {
  status: {
    connected: COLORS.green,
    reconnecting: COLORS.yellow,
    disconnected: COLORS.red,
    roomNumber: COLORS.purple,
  },
  message: {
    system: COLORS.yellow,
    gameResponse: COLORS.green,
    action: COLORS.cyan,
    selfNick: COLORS.white,
    nickColors: NICK_COLORS,
  },
  ui: {
    selected: COLORS.cyan,
    ownerName: COLORS.yellow,
    mutedName: COLORS.red,
    defaultText: COLORS.white,
    focusedField: COLORS.cyan,
  },
  symbols: {
    separator: "\u2501",
    statusDot: "\u25CF",
    slowModePrefix: "\u25B8",
    systemPrefix: "***",
    gameResponsePrefix: ">>>",
    gameCommandPrefix: " > ",
    actionPrefix: "* ",
    selectedRow: "> ",
    ownerRow: "* ",
  },
}
