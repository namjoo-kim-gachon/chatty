export interface Theme {
  readonly status: {
    readonly connected: string
    readonly reconnecting: string
    readonly disconnected: string
    readonly roomNumber: string
  }
  readonly message: {
    readonly system: string
    readonly gameResponse: string
    readonly action: string
    readonly selfNick: string
    readonly nickColors: readonly string[]
  }
  readonly ui: {
    readonly selected: string
    readonly ownerName: string
    readonly mutedName: string
    readonly defaultText: string
    readonly focusedField: string
  }
  readonly symbols: {
    readonly separator: string
    readonly statusDot: string
    readonly slowModePrefix: string
    readonly systemPrefix: string
    readonly gameResponsePrefix: string
    readonly gameCommandPrefix: string
    readonly actionPrefix: string
    readonly selectedRow: string
    readonly ownerRow: string
  }
}
