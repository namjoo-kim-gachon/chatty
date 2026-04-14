export async function setup(): Promise<void> {
  const response = await fetch("http://localhost:7799/health").catch(
    () => undefined,
  )
  if (response?.ok !== true) {
    throw new Error(
      "Server is not running. Start it first: uv run uvicorn app.main:app --port 7799 --app-dir apps/server",
    )
  }
}
