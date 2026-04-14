export interface Locale {
  readonly status: {
    readonly connected: string
    readonly reconnecting: string
    readonly disconnected: string
    readonly scrollHint: string
  }
  readonly app: {
    readonly tooNarrow: string
    readonly tooShort: string
    readonly connecting: string
    readonly loadFailed: string
    readonly banned: string
    readonly adminOnly: string
    readonly muted: string
    readonly unmuted: string
    readonly wrongPassword: string
    readonly roomLoadFailed: string
    readonly unknownCommand: string
    readonly joinFailed: string
    readonly muteNotOwner: string
    readonly muteUserNotFound: string
    readonly muteSuccess: string
    readonly unmuteSuccess: string
    readonly muteFailed: string
    readonly unmuteFailed: string
    readonly banNotOwner: string
    readonly banUserNotFound: string
    readonly banSuccess: string
    readonly unbanSuccess: string
    readonly banFailed: string
    readonly unbanFailed: string
    readonly userJoined: string
    readonly userLeft: string
  }
  readonly message: {
    readonly muted: string
  }
  readonly commands: {
    readonly rooms: string
    readonly create: string
    readonly join: string
    readonly joinArg: string
    readonly who: string
    readonly leave: string
    readonly quit: string
    readonly mute: string
    readonly muteArg: string
    readonly unmute: string
    readonly unmuteArg: string
    readonly ban: string
    readonly banArg: string
    readonly unban: string
    readonly unbanArg: string
  }
  readonly roomList: {
    readonly title: string
    readonly search: string
    readonly loading: string
    readonly noRooms: string
    readonly help: string
    readonly page: string
  }
  readonly createRoom: {
    readonly title: string
    readonly fieldName: string
    readonly fieldDescription: string
    readonly fieldPassword: string
    readonly fieldMaxMembers: string
    readonly fieldSlowMode: string
    readonly errorNameRequired: string
    readonly errorMaxRange: string
    readonly errorSlowRange: string
    readonly errorCreateFailed: string
    readonly creating: string
    readonly help: string
  }
  readonly userList: {
    readonly onlineCount: string
    readonly noUsers: string
    readonly owner: string
    readonly muted: string
    readonly help: string
    readonly helpOwner: string
    readonly page: string
  }
  readonly passwordInput: {
    readonly title: string
    readonly label: string
    readonly help: string
  }
  readonly login: {
    readonly title: string
    readonly nicknameLabel: string
    readonly oauthTitle: string
    readonly oauthOpenUrl: string
    readonly oauthWaiting: string
    readonly oauthConnecting: string
    readonly nicknameSetupTitle: string
    readonly nicknameSetupSubtitle: string
    readonly nicknameSetupLabel: string
    readonly nicknameSetupSetting: string
    readonly loggedInAs: string
    readonly newUserHint: string
    readonly oauthTimedOut: string
    readonly oauthFailed: string
    readonly nicknameSame: string
    readonly nicknameTaken: string
    readonly nicknameChangeTitle: string
    readonly nicknameChangeSubtitle: string
    readonly nicknameCmdNotLoggedIn: string
    readonly nicknameCmdChanged: string
  }
}
