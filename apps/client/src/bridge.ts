import type { Room, Message, SSEStatus, AuthState, Config } from "./types.js"

export interface AppState {
  authState: AuthState
  config: Config
  activeRoom: Room | undefined
  messages: Message[]
  userCount: number
  sseStatus: SSEStatus
  isMuted: boolean
  isBanned: boolean
  ownerNickname: string
  screen: string
}

export interface AppActions {
  enterRoom: (room: Room, password?: string) => Promise<void>
  exitRoom: () => Promise<void>
  sendMessage: (
    text: string,
  ) => Promise<{ ok: boolean; id: string; seq: number }>
}

class AppBridge {
  private stateGetter: (() => AppState) | undefined = undefined
  private actions: AppActions | undefined = undefined

  registerState(getter: () => AppState): void {
    this.stateGetter = getter
  }

  registerActions(actions: AppActions): void {
    this.actions = actions
  }

  getState(): AppState | undefined {
    return this.stateGetter?.()
  }

  getActions(): AppActions | undefined {
    return this.actions
  }

  get isReady(): boolean {
    return this.stateGetter !== undefined && this.actions !== undefined
  }
}

export const appBridge = new AppBridge()
