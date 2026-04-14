#!/usr/bin/env python3
"""Read & Auth load test.

Phase 1: GET /rooms  (concurrent room listing)
Phase 2: GET /rooms/{id}/messages  (concurrent message reads)
Phase 3: POST /auth/quick-login  (concurrent auth with bcrypt)
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta

import httpx
from jose import jwt

BASE = "http://localhost:7799"
PSQL = "/opt/homebrew/opt/postgresql@17/bin/psql"
DB_PASS = "cho9942!"
SECRET_KEY = "change-me-in-production-please"

SUCCESS_RATE = 0.95
LATENCY_P95_MAX = 3000  # ms

PHASES = [50, 100, 200, 300, 400, 500]
AUTH_PHASES = [10, 20, 30, 50, 75, 100]
STRESS_USER_PREFIX = "stress_"
STRESS_ROOM_NAME = "stress-concurrency-room"


def make_client(max_conn: int = 600, timeout: float = 30.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        limits=httpx.Limits(max_connections=max_conn, max_keepalive_connections=max_conn),
        timeout=httpx.Timeout(timeout, connect=15.0),
    )


def make_token(user_id: str, nickname: str) -> str:
    expire = datetime.now(UTC) + timedelta(hours=24)
    payload = {
        "sub": user_id,
        "nickname": nickname,
        "is_admin": False,
        "token_version": 0,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def psql_query(sql: str) -> str:
    r = subprocess.run(
        [PSQL, "-U", "postgres", "-h", "localhost", "chatty", "-t", "-A", "-c", sql],
        env={**os.environ, "PGPASSWORD": DB_PASS},
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()


def load_stress_users(count: int) -> list[tuple[str, str]]:
    raw = psql_query(
        f"SELECT id, nickname FROM users"
        f" WHERE nickname LIKE '{STRESS_USER_PREFIX}%'"
        f" ORDER BY nickname LIMIT {count};"
    )
    users = [(line.split("|")[0], line.split("|")[1]) for line in raw.splitlines() if "|" in line]
    if not users:
        print("ERROR: No stress users found. Run stress-concurrency.py first.")
        sys.exit(1)
    return users


def get_room_id() -> str:
    rid = psql_query(
        f"SELECT id FROM rooms WHERE name = '{STRESS_ROOM_NAME}' AND deleted_at IS NULL LIMIT 1;"
    )
    if not rid:
        print("ERROR: Stress room not found. Run stress-concurrency.py first.")
        sys.exit(1)
    return rid


def pct(data: list[float]) -> dict[str, float]:
    if not data:
        return {"avg": 0, "p50": 0, "p95": 0, "p99": 0}
    data.sort()
    n = len(data)
    return {
        "avg": sum(data) / n,
        "p50": data[n // 2],
        "p95": data[int(n * 0.95)],
        "p99": data[int(n * 0.99)],
    }


def fmt(s: dict[str, float]) -> str:
    return (
        f"avg={s['avg']:.0f}ms  "
        f"p50={s['p50']:.0f}ms  "
        f"p95={s['p95']:.0f}ms  "
        f"p99={s['p99']:.0f}ms"
    )


def passed(results: list[float]) -> bool:
    ok = [r for r in results if r > 0]
    rate = len(ok) / len(results) if results else 0
    return rate >= SUCCESS_RATE and pct(ok)["p95"] < LATENCY_P95_MAX


def report(results: list[float], n: int) -> None:
    ok = [r for r in results if r > 0]
    fail = len(results) - len(ok)
    rate = len(ok) / len(results) if results else 0
    stats = pct(ok)
    tag = "PASS" if passed(results) else "FAIL"
    print(f"  [{tag}] ok={len(ok)}/{n}  fail={fail}  rate={rate:.0%}")
    if ok:
        print(f"         {fmt(stats)}")


async def health_check() -> bool:
    async with make_client(max_conn=5, timeout=5) as c:
        try:
            r = await c.get(f"{BASE}/health")
            return r.status_code == 200
        except Exception:
            return False


async def timed_get(
    client: httpx.AsyncClient, url: str, token: str,
) -> float:
    t0 = time.perf_counter()
    try:
        r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        ms = (time.perf_counter() - t0) * 1000
        if r.status_code == 200:
            return ms
        print(f"    [FAIL] {r.status_code}: {r.text[:80]}", flush=True)
        return -1.0
    except Exception as e:
        print(f"    [FAIL] {type(e).__name__}", flush=True)
        return -1.0


async def timed_quick_login(client: httpx.AsyncClient, nickname: str) -> float:
    t0 = time.perf_counter()
    try:
        r = await client.post(
            f"{BASE}/auth/quick-login",
            json={"nickname": nickname},
        )
        ms = (time.perf_counter() - t0) * 1000
        if r.status_code in (200, 201):
            return ms
        print(f"    [FAIL] {r.status_code}: {r.text[:80]}", flush=True)
        return -1.0
    except Exception as e:
        print(f"    [FAIL] {type(e).__name__}", flush=True)
        return -1.0


async def run_phase(
    label: str,
    phases: list[int],
    make_tasks: object,  # callable(client, n) -> list[coroutine]
) -> int:
    best = 0
    for n in phases:
        await asyncio.sleep(1)
        async with make_client(max_conn=n + 20) as c:
            tasks = make_tasks(c, n)  # type: ignore[operator]
            results_raw = await asyncio.gather(*tasks)
        results = list(results_raw)
        print(f"  n={n}:")
        report(results, n)
        if passed(results):
            best = n
        else:
            break
    return best


async def main() -> None:
    print(f"\n{'=' * 60}")
    print("  Read & Auth Load Test")
    print(f"  Criteria: {SUCCESS_RATE:.0%} success, p95 < {LATENCY_P95_MAX}ms")
    print(f"{'=' * 60}\n")

    if not await health_check():
        print("ERROR: server not reachable")
        sys.exit(1)

    t0 = time.perf_counter()
    users = load_stress_users(max(PHASES))
    room_id = get_room_id()
    tokens = [make_token(uid, nick) for uid, nick in users]
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  Setup: {len(users)} users, room={room_id[:8]}... ({elapsed:.0f}ms)\n")

    # ── Phase 1: GET /rooms ──
    print(f"{'─' * 60}")
    print("  Phase 1: GET /rooms (room listing)")
    print(f"{'─' * 60}")
    best1 = await run_phase(
        "GET /rooms",
        PHASES,
        lambda c, n: [
            timed_get(c, f"{BASE}/rooms", tokens[i]) for i in range(n)
        ],
    )
    print(f"  >> Max concurrent GET /rooms: {best1}\n")

    # ── Phase 2: GET /rooms/{id}/messages ──
    print(f"{'─' * 60}")
    print("  Phase 2: GET /rooms/{id}/messages (message reads)")
    print(f"{'─' * 60}")
    best2 = await run_phase(
        "GET /messages",
        PHASES,
        lambda c, n: [
            timed_get(c, f"{BASE}/rooms/{room_id}/messages", tokens[i])
            for i in range(n)
        ],
    )
    print(f"  >> Max concurrent GET /messages: {best2}\n")

    # ── Phase 3: POST /auth/quick-login (bcrypt-bound) ──
    print(f"{'─' * 60}")
    print("  Phase 3: POST /auth/quick-login (bcrypt CPU-bound)")
    print(f"{'─' * 60}")
    ts = int(time.time())
    cursor = 0

    def make_auth_tasks(c: httpx.AsyncClient, n: int) -> list[object]:
        nonlocal cursor
        tasks = [
            timed_quick_login(c, f"authtest_{ts}_{cursor + i}")
            for i in range(n)
        ]
        cursor += n
        return tasks

    best3 = await run_phase("quick-login", AUTH_PHASES, make_auth_tasks)
    print(f"  >> Max concurrent quick-login: {best3}\n")

    # ── Summary ──
    print(f"{'=' * 60}")
    print(f"  GET /rooms          : {best1}")
    print(f"  GET /messages       : {best2}")
    print(f"  POST /auth/quick-login : {best3}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
