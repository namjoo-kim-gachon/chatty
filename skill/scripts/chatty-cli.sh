#!/usr/bin/env bash
# Wrapper script for chatty-cli
# Priority: 1) PATH (npm global install)  2) local dist build  3) tsx source

set -euo pipefail

# 1) npm global install or any chatty-cli in PATH
if command -v chatty-cli >/dev/null 2>&1; then
  exec chatty-cli "$@"
fi

# 2) local dist build
CHATTY_DIR="${CHATTY_PROJECT_DIR:-/Users/namjookim/projects/chatty}"
DIST_CLI="${CHATTY_DIR}/apps/client/dist/cli.js"

if [ -f "$DIST_CLI" ]; then
  exec node "$DIST_CLI" "$@"
fi

# 3) tsx fallback (dev mode)
SRC_CLI="${CHATTY_DIR}/apps/client/src/cli.ts"

if [ ! -f "$SRC_CLI" ]; then
  echo "Error: chatty-cli not found. Install via 'npm install -g chatty-app' or set CHATTY_PROJECT_DIR." >&2
  exit 1
fi

TSX_BIN="${CHATTY_DIR}/node_modules/.bin/tsx"
if [ ! -x "$TSX_BIN" ]; then
  TSX_BIN="$(command -v tsx 2>/dev/null || true)"
fi

if [ -z "$TSX_BIN" ]; then
  echo "Error: tsx not found. Run 'npm install' in ${CHATTY_DIR}" >&2
  exit 1
fi

exec "$TSX_BIN" "$SRC_CLI" "$@"
