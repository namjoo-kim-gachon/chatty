import type { Theme } from "./types.js"

const COLORS = {
  green: "green",
  yellow: "yellow",
  cyan: "cyan",
  red: "red",
  white: "white",
  magenta: "magenta",
  blue: "blue",
  brightCyan: "cyanBright",
  brightGreen: "greenBright",
  brightMagenta: "magentaBright",
  brightBlue: "blueBright",
  brightRed: "redBright",
  brightWhite: "whiteBright",
} as const

const NICK_COLORS = [
  COLORS.cyan,
  COLORS.green,
  COLORS.magenta,
  COLORS.blue,
  COLORS.red,
  COLORS.brightCyan,
  COLORS.brightGreen,
  COLORS.brightMagenta,
  COLORS.brightBlue,
  COLORS.brightRed,
] as const

export const defaultTheme: Theme = {
  status: {
    connected: COLORS.green,
    reconnecting: COLORS.yellow,
    disconnected: COLORS.red,
    roomNumber: COLORS.yellow,
  },
  message: {
    system: COLORS.yellow,
    gameResponse: COLORS.green,
    action: COLORS.cyan,
    selfNick: COLORS.brightWhite,
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
    separator: "-",
    statusDot: "*",
    slowModePrefix: "\u25B8",
    systemPrefix: "***",
    gameResponsePrefix: ">>>",
    gameCommandPrefix: " > ",
    actionPrefix: "* ",
    selectedRow: "> ",
    ownerRow: "* ",
  },
}
