#!/usr/bin/env bash
set -euo pipefail

echo "Initializing chatty development environment..."

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Sync Python dependencies
cd "$(dirname "$0")/.."
uv sync

echo "Done! Run 'uv run uvicorn app.main:app --reload --port 7799 --app-dir apps/server' to start the server."
