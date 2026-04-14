#!/usr/bin/env python3
"""Chatty concurrent connection stress test."""

from __future__ import annotations

import asyncio
import time

import httpx

BASE = "http://localhost:7799"
ROOM = "general"
PHASES = [50, 100, 200, 500]


def make_client(max_conn: int = 600, timeout: float = 30.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        limits=httpx.Limits(
            max_connections=max_conn,
            max_keepalive_connections=max_conn,
        ),
        timeout=httpx.Timeout(timeout, connect=10.0),
    )


async def quick_login(client: httpx.AsyncClient, idx: int, retries: int = 3) -> dict[str, str]:
    nick = f"stress{idx}_{int(time.time())}"
    for attempt in range(retries):
        try:
            resp = await client.post(
                f"{BASE}/auth/quick-login", json={"nickname": nick}
            )
            resp.raise_for_status()
            data = resp.json()
            return {"token": data["access_token"], "nickname": nick}
        except Exception:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(0.5 * (attempt + 1))
    raise RuntimeError("unreachable")


async def join_room(client: httpx.AsyncClient, token: str, room: str) -> None:
    resp = await client.post(
        f"{BASE}/rooms/{room}/join",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    if resp.status_code not in (200, 409):
        resp.raise_for_status()


async def send_message(
    client: httpx.AsyncClient, token: str, room: str, text: str
) -> float:
    t0 = time.perf_counter()
    resp = await client.post(
        f"{BASE}/rooms/{room}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"text": text},
    )
    elapsed = (time.perf_counter() - t0) * 1000
    resp.raise_for_status()
    return elapsed


async def connect_sse(token: str, room: str, timeout: float = 8.0) -> float:
    """Open SSE, read first line, close. Returns connect time in ms."""
    url = f"{BASE}/rooms/{room}/stream?token={token}"
    t0 = time.perf_counter()
    async with make_client(max_conn=10, timeout=timeout) as client:
        try:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                elapsed = (time.perf_counter() - t0) * 1000
                async for _ in resp.aiter_lines():
                    break
                return elapsed
        except Exception:
            return -1.0


async def sse_listen(
    token: str,
    room: str,
    target_text: str,
    ready_event: asyncio.Event,
    timeout: float = 20.0,
) -> float:
    """Listen SSE until target_text arrives. Returns delivery time in ms."""
    url = f"{BASE}/rooms/{room}/stream?token={token}"
    async with make_client(max_conn=10, timeout=timeout) as client:
        try:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                ready_event.set()
                t0 = time.perf_counter()
                async for line in resp.aiter_lines():
                    if target_text in line:
                        return (time.perf_counter() - t0) * 1000
        except Exception:
            pass
    return -1.0


def percentiles(data: list[float]) -> str:
    if not data:
        return "no data"
    data.sort()
    n = len(data)
    p50 = data[n // 2]
    p95 = data[int(n * 0.95)]
    p99 = data[int(n * 0.99)]
    avg = sum(data) / n
    return f"avg={avg:.0f}ms  p50={p50:.0f}ms  p95={p95:.0f}ms  p99={p99:.0f}ms"


def print_header(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


async def phase1_sse_connect(n: int, users: list[dict[str, str]]) -> None:
    """Phase 1: Concurrent SSE connections (each with own client)."""
    print(f"\n  Phase 1: {n} concurrent SSE connections")
    subset = users[:n]

    # Each SSE gets its own client to avoid pool contention
    sem = asyncio.Semaphore(min(n, 200))

    async def limited(token: str) -> float:
        async with sem:
            return await connect_sse(token, ROOM)

    results = await asyncio.gather(*[limited(u["token"]) for u in subset])

    ok = [r for r in results if r >= 0]
    fail = len(results) - len(ok)
    print(f"    Success: {len(ok)}/{n}  Fail: {fail}")
    if ok:
        print(f"    Latency: {percentiles(ok)}")


async def phase2_message_send(n: int, users: list[dict[str, str]]) -> None:
    """Phase 2: Concurrent message POSTs."""
    print(f"\n  Phase 2: {n} concurrent message POSTs")
    subset = users[:n]

    async with make_client() as client:
        tasks = [
            send_message(client, u["token"], ROOM, f"stress-{i}")
            for i, u in enumerate(subset)
        ]
        t0 = time.perf_counter()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        wall = time.perf_counter() - t0

    latencies: list[float] = []
    errors = 0
    for r in results:
        if isinstance(r, float):
            latencies.append(r)
        else:
            errors += 1

    throughput = len(latencies) / wall if wall > 0 else 0
    print(f"    Success: {len(latencies)}/{n}  Errors: {errors}")
    if latencies:
        print(f"    Latency: {percentiles(latencies)}")
        print(f"    Throughput: {throughput:.0f} req/s  Wall: {wall:.1f}s")


async def phase3_fanout(n: int, users: list[dict[str, str]]) -> None:
    """Phase 3: SSE fan-out delay."""
    print(f"\n  Phase 3: Fan-out to {n} SSE listeners")
    sender = users[0]
    listeners = users[1:n]
    marker = f"fanout-{n}-{int(time.time())}"

    ready_events = [asyncio.Event() for _ in listeners]

    # Each listener gets its own client
    listen_tasks = [
        asyncio.create_task(
            sse_listen(u["token"], ROOM, marker, ev)
        )
        for u, ev in zip(listeners, ready_events)
    ]

    # Wait for listeners to connect
    try:
        await asyncio.wait_for(
            asyncio.gather(*(ev.wait() for ev in ready_events)),
            timeout=15.0,
        )
    except asyncio.TimeoutError:
        connected = sum(1 for ev in ready_events if ev.is_set())
        print(f"    Only {connected}/{len(listeners)} listeners connected in time")

    await asyncio.sleep(0.5)

    # Send marker with a fresh client
    try:
        async with make_client() as client:
            await send_message(client, sender["token"], ROOM, marker)
    except Exception as e:
        print(f"    Failed to send marker: {e}")
        for t in listen_tasks:
            t.cancel()
        return

    # Collect results
    done, pending = await asyncio.wait(listen_tasks, timeout=15.0)
    for p in pending:
        p.cancel()

    deliveries: list[float] = []
    for t in done:
        try:
            r = t.result()
            if r >= 0:
                deliveries.append(r)
        except Exception:
            pass

    total = len(listeners)
    print(f"    Received: {len(deliveries)}/{total}")
    if deliveries:
        print(f"    Delivery: {percentiles(deliveries)}")


async def phase4_mixed(
    n: int, users: list[dict[str, str]], duration: float = 10.0
) -> None:
    """Phase 4: Mixed workload for sustained period."""
    print(f"\n  Phase 4: Mixed workload ({n} users, {duration:.0f}s)")
    subset = users[:n]

    msg_latencies: list[float] = []
    room_latencies: list[float] = []
    errors = 0
    deadline = time.perf_counter() + duration

    async with make_client() as client:

        async def message_worker(user: dict[str, str]) -> None:
            nonlocal errors
            seq = 0
            while time.perf_counter() < deadline:
                seq += 1
                try:
                    lat = await send_message(
                        client, user["token"], ROOM,
                        f"m-{user['nickname']}-{seq}",
                    )
                    msg_latencies.append(lat)
                except Exception:
                    errors += 1
                await asyncio.sleep(0.1)

        async def rooms_worker(user: dict[str, str]) -> None:
            nonlocal errors
            while time.perf_counter() < deadline:
                try:
                    t0 = time.perf_counter()
                    resp = await client.get(
                        f"{BASE}/rooms",
                        headers={"Authorization": f"Bearer {user['token']}"},
                    )
                    resp.raise_for_status()
                    room_latencies.append(
                        (time.perf_counter() - t0) * 1000
                    )
                except Exception:
                    errors += 1
                await asyncio.sleep(0.2)

        half = max(1, n // 2)
        tasks: list[asyncio.Task[None]] = []
        for u in subset[:half]:
            tasks.append(asyncio.create_task(message_worker(u)))
        for u in subset[half:]:
            tasks.append(asyncio.create_task(rooms_worker(u)))

        await asyncio.gather(*tasks)

    total_ops = len(msg_latencies) + len(room_latencies)
    print(f"    Total ops: {total_ops}  Errors: {errors}")
    if msg_latencies:
        print(f"    POST msg: {percentiles(msg_latencies)}  ({len(msg_latencies)} reqs)")
    if room_latencies:
        print(f"    GET rooms: {percentiles(room_latencies)}  ({len(room_latencies)} reqs)")


async def main() -> None:
    print_header("Chatty Stress Test")
    print(f"  Server: {BASE}")
    print(f"  Room: {ROOM}")
    print(f"  Phases: {PHASES}")

    max_users = max(PHASES)

    # Clear any leftover mutes from previous runs
    print("\n  Clearing old mutes...")
    import subprocess
    subprocess.run(
        [
            "/opt/homebrew/opt/postgresql@17/bin/psql",
            "-U", "postgres", "-h", "localhost", "chatty",
            "-c", "DELETE FROM room_mutes;",
        ],
        env={**__import__("os").environ, "PGPASSWORD": "cho9942!"},
        capture_output=True,
    )

    print(f"  Creating {max_users} users...")

    users: list[dict[str, str]] = []
    async with make_client() as client:
        batch_size = 20
        for batch_start in range(0, max_users, batch_size):
            batch_end = min(batch_start + batch_size, max_users)
            batch = await asyncio.gather(
                *[quick_login(client, i) for i in range(batch_start, batch_end)]
            )
            users.extend(batch)
            print(f"    Created {len(users)}/{max_users} users")

        print(f"  Joining {max_users} users to #{ROOM}...")
        for batch_start in range(0, max_users, batch_size):
            batch_end = min(batch_start + batch_size, max_users)
            await asyncio.gather(
                *[
                    join_room(client, u["token"], ROOM)
                    for u in users[batch_start:batch_end]
                ]
            )
        print("    All joined.")

    def clear_mutes() -> None:
        import subprocess
        subprocess.run(
            [
                "/opt/homebrew/opt/postgresql@17/bin/psql",
                "-U", "postgres", "-h", "localhost", "chatty",
                "-c", "DELETE FROM room_mutes;",
            ],
            env={**__import__("os").environ, "PGPASSWORD": "cho9942!"},
            capture_output=True,
        )

    for n in PHASES:
        print_header(f"Scale: {n} users")
        clear_mutes()
        await phase1_sse_connect(n, users)
        clear_mutes()
        await phase2_message_send(n, users)
        clear_mutes()
        if n <= 200:
            await phase3_fanout(n, users)
        else:
            print(f"\n  Phase 3: Skipped at {n} (too many open streams for httpx)")
        clear_mutes()
        dur = 10.0 if n <= 200 else 15.0
        await phase4_mixed(n, users, duration=dur)

    print_header("Done")


if __name__ == "__main__":
    asyncio.run(main())
