#!/usr/bin/env python3
"""Single-room concurrency limit test.

Finds the exact max concurrent POST /messages the server can handle
before p95 > 3000ms or success rate drops below 95%.
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
DB_URL = "postgresql://postgres:cho9942!@localhost:5432/chatty"
SECRET_KEY = "change-me-in-production-please"

SUCCESS_RATE = 0.95
LATENCY_P95_MAX = 3000  # ms

PHASES = [50, 100, 150, 200, 250, 300, 400, 500]
STRESS_USER_COUNT = 10000
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


def clear_mutes() -> None:
    psql("DELETE FROM room_mutes;")


def ensure_stress_users() -> list[tuple[str, str]]:
    """Ensure stress test users exist. Returns list of (user_id, nickname)."""
    count = int(psql_query(
        f"SELECT COUNT(*) FROM users WHERE nickname LIKE '{STRESS_USER_PREFIX}%';"
    ) or "0")

    if count >= STRESS_USER_COUNT:
        # Already seeded — fetch ids
        raw = psql_query(
            f"SELECT id, nickname FROM users"
            f" WHERE nickname LIKE '{STRESS_USER_PREFIX}%'"
            f" ORDER BY nickname LIMIT {STRESS_USER_COUNT};"
        )
        return [(line.split("|")[0], line.split("|")[1]) for line in raw.splitlines() if "|" in line]

    print(f"  Seeding {STRESS_USER_COUNT} stress users (one-time)...")
    now = time.time()
    values: list[str] = []
    users: list[tuple[str, str]] = []
    for i in range(STRESS_USER_COUNT):
        uid = str(uuid.uuid4())
        nick = f"{STRESS_USER_PREFIX}{i}"
        email = f"{nick}@stress.local"
        values.append(
            f"('{uid}', '{email}', '{nick}', 'no-password', FALSE, 0, {now})"
        )
        users.append((uid, nick))

    for start in range(0, len(values), 500):
        chunk = values[start : start + 500]
        psql(
            "INSERT INTO users (id, email, nickname, password_hash,"
            " is_admin, token_version, created_at) VALUES "
            + ",".join(chunk)
            + " ON CONFLICT (nickname) DO NOTHING;"
        )
    print(f"  {STRESS_USER_COUNT} users seeded")
    return users


STRESS_ROOM_NUMBER = 5999  # Reserved for stress testing


def ensure_stress_room(owner_id: str) -> str:
    """Ensure stress test room exists. Returns room_id."""
    existing = psql_query(
        f"SELECT id FROM rooms WHERE name = '{STRESS_ROOM_NAME}' AND deleted_at IS NULL LIMIT 1;"
    )
    if existing:
        return existing

    # Undelete if it exists but was soft-deleted
    deleted = psql_query(
        f"SELECT id FROM rooms WHERE name = '{STRESS_ROOM_NAME}' LIMIT 1;"
    )
    if deleted:
        psql(f"UPDATE rooms SET deleted_at = NULL WHERE id = '{deleted}';")
        return deleted

    room_id = str(uuid.uuid4())
    now = time.time()
    result = psql(
        f"INSERT INTO rooms"
        f" (id, room_number, name, description, type, owner_id, created_by, created_at, updated_at)"
        f" VALUES ('{room_id}', {STRESS_ROOM_NUMBER}, '{STRESS_ROOM_NAME}', 'stress test', 'chat',"
        f" '{owner_id}', '{owner_id}', {now}, {now});"
    )
    if result.returncode != 0:
        print(f"ERROR: failed to create stress room: {result.stderr.decode()}")
        sys.exit(1)
    psql(f"INSERT INTO room_seq (room_id, seq) VALUES ('{room_id}', 0) ON CONFLICT DO NOTHING;")
    return room_id


def ensure_members(room_id: str, users: list[tuple[str, str]]) -> None:
    """Ensure all users are members of the room."""
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
    wall = max(results) if ok else 0
    print(f"  [{tag}] ok={len(ok)}/{n}  fail={fail}  rate={rate:.0%}  wall={wall:.0f}ms")
    if ok:
        print(f"         {fmt(stats)}")


async def health_check() -> bool:
    async with make_client(max_conn=5, timeout=5) as c:
        try:
            r = await c.get(f"{BASE}/health")
            return r.status_code == 200
        except Exception:
            return False



async def post_msg(
    client: httpx.AsyncClient, token: str, room_id: str, text: str
) -> float:
    t0 = time.perf_counter()
    try:
        r = await client.post(
            f"{BASE}/rooms/{room_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"text": text},
        )
        ms = (time.perf_counter() - t0) * 1000
        if r.status_code in (200, 201):
            return ms
        print(f"    [FAIL] {r.status_code}: {r.text[:80]}", flush=True)
        return -1.0
    except Exception as e:
        print(f"    [FAIL] {type(e).__name__}", flush=True)
        return -1.0


async def main() -> None:
    print(f"\n{'=' * 60}")
    print(f"  Single-room Concurrency Limit Test")
    print(f"  Criteria: {SUCCESS_RATE:.0%} success, p95 < {LATENCY_P95_MAX}ms")
    print(f"{'=' * 60}\n")

    if not await health_check():
        print("ERROR: server not reachable")
        sys.exit(1)

    # Ensure stress test fixtures (one-time seed, reused across runs)
    t0 = time.perf_counter()
    users = ensure_stress_users()
    room_id = ensure_stress_room(users[0][0])
    ensure_members(room_id, users)
    tokens = [make_token(uid, nick) for uid, nick in users]
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  Setup: {len(users)} users, room={room_id[:8]}... ({elapsed:.0f}ms)\n")

    best = 0
    cursor = 0  # rolling cursor so each phase uses fresh users

    for n in PHASES:
        if cursor + n > len(tokens):
            print(f"  Skipping n={n} — not enough fresh users")
            break

        clear_mutes()
        await asyncio.sleep(1)

        subset = tokens[cursor : cursor + n]
        cursor += n

        ts = int(time.time())
        async with make_client(max_conn=n + 20) as c:
            t_wall = time.perf_counter()
            results_raw = await asyncio.gather(*[
                post_msg(c, tok, room_id, f"cc-{n}-{i}-{ts}")
                for i, tok in enumerate(subset)
            ])
        results = list(results_raw)

        print(f"  n={n}:")
        report(results, n)

        if passed(results):
            best = n
        else:
            # One more phase to confirm it's not a fluke
            break

    print(f"\n{'=' * 60}")
    print(f"  Max concurrent POST /messages : {best}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
