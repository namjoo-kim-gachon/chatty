#!/usr/bin/env python3
"""Find the max concurrent SSE connections the server can sustain.

Reuses the stress_* users seeded by stress-concurrency.py.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from jose import jwt

BASE = "http://localhost:7799"
PSQL = "/opt/homebrew/opt/postgresql@17/bin/psql"
DB_PASS = "cho9942!"
SECRET_KEY = "change-me-in-production-please"

SUCCESS_RATE = 0.95
LATENCY_P95_MAX = 3000  # ms

PHASES = [500, 1000, 1500, 2000, 2500, 3000, 4000, 5000]
STRESS_USER_PREFIX = "stress_"
STRESS_ROOM_NAME = "stress-sse-room"


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


def psql(sql: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [PSQL, "-U", "postgres", "-h", "localhost", "chatty", "-c", sql],
        env={**os.environ, "PGPASSWORD": DB_PASS},
        capture_output=True,
    )


def psql_query(sql: str) -> str:
    r = subprocess.run(
        [PSQL, "-U", "postgres", "-h", "localhost", "chatty", "-t", "-A", "-c", sql],
        env={**os.environ, "PGPASSWORD": DB_PASS},
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()


def load_stress_users(count: int) -> list[tuple[str, str]]:
    """Load existing stress users from DB. Assumes they were seeded already."""
    raw = psql_query(
        f"SELECT id, nickname FROM users"
        f" WHERE nickname LIKE '{STRESS_USER_PREFIX}%'"
        f" ORDER BY nickname LIMIT {count};"
    )
    users = [(line.split("|")[0], line.split("|")[1]) for line in raw.splitlines() if "|" in line]
    if not users:
        print("ERROR: No stress users found. Run stress-concurrency.py first to seed users.")
        sys.exit(1)
    return users


def ensure_stress_room(owner_id: str) -> str:
    existing = psql_query(
        f"SELECT id FROM rooms WHERE name = '{STRESS_ROOM_NAME}' AND deleted_at IS NULL LIMIT 1;"
    )
    if existing:
        return existing

    room_id = str(uuid.uuid4())
    now = time.time()
    psql(
        f"INSERT INTO rooms (id, name, description, type, owner_id, created_by, created_at, updated_at)"
        f" VALUES ('{room_id}', '{STRESS_ROOM_NAME}', 'sse stress test', 'chat',"
        f" '{owner_id}', '{owner_id}', {now}, {now});"
    )
    return room_id


def ensure_members(room_id: str, users: list[tuple[str, str]]) -> None:
    count = int(psql_query(
        f"SELECT COUNT(*) FROM room_members WHERE room_id = '{room_id}';"
    ) or "0")
    if count >= len(users):
        return

    now = time.time()
    join_values = [f"('{uid}', '{room_id}', {now})" for uid, _ in users]
    for start in range(0, len(join_values), 500):
        chunk = join_values[start : start + 500]
        psql(
            "INSERT INTO room_members (user_id, room_id, joined_at) VALUES "
            + ",".join(chunk)
            + " ON CONFLICT DO NOTHING;"
        )


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
    stats = pct(ok)
    return rate >= SUCCESS_RATE and stats["p95"] < LATENCY_P95_MAX


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


async def sse_connect(token: str, room_id: str, timeout: float = 15.0) -> float:
    """Open SSE stream, read first event, return connect time in ms. -1 on fail."""
    t0 = time.perf_counter()
    try:
        async with make_client(max_conn=2, timeout=timeout) as c:
            async with c.stream(
                "GET",
                f"{BASE}/rooms/{room_id}/stream",
                params={"token": token},
            ) as resp:
                if resp.status_code != 200:
                    print(f"    [FAIL] status={resp.status_code}", flush=True)
                    return -1.0
                async for line in resp.aiter_lines():
                    if line.startswith("data:") or line.startswith("event:"):
                        return (time.perf_counter() - t0) * 1000
                return (time.perf_counter() - t0) * 1000
    except Exception as e:
        print(f"    [FAIL] {type(e).__name__}", flush=True)
        return -1.0


async def main() -> None:
    print(f"\n{'=' * 60}")
    print("  SSE Connection Limit Test")
    print(f"  Criteria: {SUCCESS_RATE:.0%} success, p95 < {LATENCY_P95_MAX}ms")
    print(f"{'=' * 60}\n")

    if not await health_check():
        print("ERROR: server not reachable")
        sys.exit(1)

    max_n = max(PHASES)
    t0 = time.perf_counter()
    users = load_stress_users(max_n)
    room_id = ensure_stress_room(users[0][0])
    ensure_members(room_id, users)
    tokens = [make_token(uid, nick) for uid, nick in users]
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  Setup: {len(users)} users, room={room_id[:8]}... ({elapsed:.0f}ms)\n")

    best = 0

    for n in PHASES:
        if n > len(tokens):
            print(f"  Skipping n={n} -- not enough users ({len(tokens)} available)")
            break

        subset = tokens[:n]
        sem = asyncio.Semaphore(300)

        async def _connect(tok: str) -> float:
            async with sem:
                return await sse_connect(tok, room_id)

        print(f"  n={n} SSE connections...")
        results_raw = await asyncio.gather(*[_connect(t) for t in subset])
        results = list(results_raw)

        report(results, n)

        if passed(results):
            best = n
        else:
            break

        await asyncio.sleep(3)

    print(f"\n{'=' * 60}")
    print(f"  Max SSE connections: {best}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
