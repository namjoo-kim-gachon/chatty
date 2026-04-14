import { execSync } from "node:child_process"
import path from "node:path"
import { fileURLToPath } from "node:url"

const fileDirectory = fileURLToPath(new URL(".", import.meta.url))
const CLIENT_ROOT = path.resolve(fileDirectory, "../..")
const REPO_ROOT = path.resolve(fileDirectory, "../../../..")
const TSX_BIN = path.join(REPO_ROOT, "node_modules", ".bin", "tsx")

const TMUX_KEYS: Record<string, string> = {
  enter: "Enter",
  tab: "Tab",
  shiftTab: "BTab",
  ctrlC: "C-c",
  ctrlR: "C-r",
  pageUp: "PPage",
  pageDown: "NPage",
  end: "End",
  up: "Up",
  down: "Down",
  escape: "Escape",
}

export type SpecialKey = keyof typeof TMUX_KEYS

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

let sessionCounter = 0

export class TmuxHarness {
  private readonly session: string
  readonly cols: number
  readonly rows: number

  constructor(
    configPath: string,
    {
      cols = 120,
      rows = 30,
      env = {},
    }: { cols?: number; rows?: number; env?: Record<string, string> } = {},
  ) {
    this.cols = cols
    this.rows = rows
    this.session = `chatty-e2e-${process.pid.toString()}-${(sessionCounter++).toString()}`

    const escaped = configPath.replaceAll("'", String.raw`'\''`)
    const tsx = TSX_BIN.replaceAll("'", String.raw`'\''`)

    const envPrefix = Object.entries(env)
      .map(([k, v]) => `${k}='${v.replaceAll("'", String.raw`'\''`)}'`)
      .join(" ")
    const envStr = envPrefix.length > 0 ? `${envPrefix} ` : ""

    execSync(
      [
        "tmux new-session -d",
        `-s '${this.session}'`,
        `-x ${this.cols.toString()}`,
        `-y ${this.rows.toString()}`,
        `"${envStr}CHATTY_CONFIG='${escaped}' FORCE_COLOR=1 TERM=xterm-256color '${tsx}' src/index.tsx; sleep 2"`,
      ].join(" "),
      { cwd: CLIENT_ROOT, env: { ...process.env, TERM: "xterm-256color" } },
    )
  }

  /** Visible pane content (plain text, no ANSI). */
  screen(): string {
    try {
      return execSync(
        `tmux capture-pane -t '${this.session}' -p -S - 2>/dev/null`,
        { encoding: "utf8" },
      )
    } catch {
      return ""
    }
  }

  /** Visible pane content with ANSI escape sequences (for color assertions). */
  screenAnsi(): string {
    try {
      return execSync(
        `tmux capture-pane -t '${this.session}' -p -e -S - 2>/dev/null`,
        { encoding: "utf8" },
      )
    } catch {
      return ""
    }
  }

  lines(): string[] {
    return this.screen().split("\n")
  }

  async waitFor(
    predicate: (screen: string) => boolean,
    timeout = 5000,
  ): Promise<void> {
    const start = Date.now()
    while (Date.now() - start < timeout) {
      if (predicate(this.screen())) return
      await sleep(100)
    }
    throw new Error(
      `waitFor timeout (${timeout.toString()}ms)\n--- screen ---\n${this.screen()}\n--------------`,
    )
  }

  async waitForText(text: string, timeout = 10_000): Promise<void> {
    await this.waitFor((s) => s.includes(text), timeout)
  }

  /** Type literal text (no key-name interpretation). */
  type(text: string): void {
    const escaped = text.replaceAll("'", String.raw`'\''`)
    execSync(`tmux send-keys -t '${this.session}' -l '${escaped}'`)
  }

  /** Press a special key. */
  press(key: SpecialKey): void {
    const mapped = TMUX_KEYS[key]
    if (mapped === undefined) throw new Error(`Unknown key: ${key}`)
    execSync(`tmux send-keys -t '${this.session}' ${mapped}`)
  }

  /** Resize the terminal to new dimensions. */
  resize(cols: number, rows: number): void {
    execSync(
      `tmux resize-window -t '${this.session}' -x ${cols.toString()} -y ${rows.toString()}`,
    )
  }

  /** Clear tmux scrollback history. */
  clearBuffer(): void {
    try {
      execSync(`tmux clear-history -t '${this.session}'`)
    } catch {
      // Session may be gone
    }
  }

  /** Kill the tmux session. */
  async kill(): Promise<void> {
    try {
      execSync(`tmux kill-session -t '${this.session}' 2>/dev/null`)
    } catch {
      // Already dead
    }
    await sleep(100)
  }
}
