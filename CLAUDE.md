# Chatty -- Claude Code Instructions

## Project Structure
- Monorepo: `apps/server/` (Python/FastAPI), `apps/client/` (TypeScript/Ink TUI, not yet implemented)
- Python package management: `uv` only (no pip)
- Run uv commands from project root (`/Users/namjookim/projects/chatty/`)

## Dev Server
```bash
cd /Users/namjookim/projects/chatty
uv run uvicorn app.main:app --reload --port 7799 --app-dir apps/server
```

## Running Tests
```bash
cd /Users/namjookim/projects/chatty
uv run pytest apps/server/tests/ -v
```

## Code Style
- Lint/format with ruff
- basedpyright strict type checking
- No `any` type, no `# type: ignore`
