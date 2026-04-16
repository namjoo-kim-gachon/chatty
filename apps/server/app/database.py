from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, LiteralString, cast

import psycopg
from psycopg import sql as pgsql
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import settings

logger = logging.getLogger(__name__)

_migration_path = Path(__file__).parent.parent / "migrations" / "001_initial.sql"

Row = dict[str, Any]
type DBConn = psycopg.AsyncConnection[Any]

_pool: AsyncConnectionPool[psycopg.AsyncConnection[Row]] | None = None
# Test-only override: when set, get_db yields this directly instead of using pool
_test_conn: psycopg.AsyncConnection[Any] | None = None

_ACQUIRE_WARN_MS = 100

LOBBY_ROOM_ID = "lobby"

_DEFAULT_ROOMS = [
    # (id, room_number, name, type, description)
    ("lobby", 0, "lobby", "chat", "Lobby -- default entry room"),
    ("general", 1, "general", "chat", "General chat room for everyone"),
    ("random", 2, "random", "chat", "Free talk, no specific topic"),
]

_DEFAULT_ROOM_ATTRS: list[tuple[str, str, str]] = [
    # (room_id, key, value)
    ("lobby", "admin_only", "true"),
]


# ---------------------------------------------------------------------------
# Sync helpers -- test infrastructure only
# ---------------------------------------------------------------------------


def _make_conn(db_url: str) -> psycopg.Connection[Row]:
    # Cast: psycopg stubs don't expose overloads for dict_row row_factory
    return cast("psycopg.Connection[Row]", psycopg.connect(db_url, autocommit=False))


def _seed(conn: psycopg.Connection[Row]) -> None:
    now = time.time()
    system_id = "00000000-0000-0000-0000-000000000000"
    conn.execute(
        """
        INSERT INTO users
          (id, email, nickname, is_admin, created_at)
        VALUES (%s, 'system@chatty.internal', 'system', TRUE, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (system_id, now),
    )
    for room_id, room_number, name, room_type, desc in _DEFAULT_ROOMS:
        conn.execute(
            """
            INSERT INTO rooms
              (id, room_number, name, type, description,
               owner_id, created_by, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                room_id,
                room_number,
                name,
                room_type,
                desc,
                system_id,
                system_id,
                now,
                now,
            ),
        )
        conn.execute(
            "INSERT INTO room_seq (room_id, seq) VALUES (%s, 0)"
            " ON CONFLICT (room_id) DO NOTHING",
            (room_id,),
        )
    for room_id, key, value in _DEFAULT_ROOM_ATTRS:
        conn.execute(
            "INSERT INTO room_attrs (room_id, key, value) VALUES (%s, %s, %s)"
            " ON CONFLICT (room_id, key) DO NOTHING",
            (room_id, key, value),
        )
    conn.commit()


def _run_migration(conn: psycopg.Connection[Row]) -> None:
    sql = _migration_path.read_text()
    for statement in sql.split(";"):
        stmt = statement.strip()
        if stmt:
            conn.execute(pgsql.SQL(cast("LiteralString", stmt)))
    conn.commit()


# ---------------------------------------------------------------------------
# Async helpers -- production use
# ---------------------------------------------------------------------------


async def _aseed(conn: psycopg.AsyncConnection[Row]) -> None:
    now = time.time()
    system_id = "00000000-0000-0000-0000-000000000000"
    await conn.execute(
        """
        INSERT INTO users
          (id, email, nickname, is_admin, created_at)
        VALUES (%s, 'system@chatty.internal', 'system', TRUE, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (system_id, now),
    )
    for room_id, room_number, name, room_type, desc in _DEFAULT_ROOMS:
        await conn.execute(
            """
            INSERT INTO rooms
              (id, room_number, name, type, description,
               owner_id, created_by, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                room_id,
                room_number,
                name,
                room_type,
                desc,
                system_id,
                system_id,
                now,
                now,
            ),
        )
        await conn.execute(
            "INSERT INTO room_seq (room_id, seq) VALUES (%s, 0)"
            " ON CONFLICT (room_id) DO NOTHING",
            (room_id,),
        )
    for room_id, key, value in _DEFAULT_ROOM_ATTRS:
        await conn.execute(
            "INSERT INTO room_attrs (room_id, key, value) VALUES (%s, %s, %s)"
            " ON CONFLICT (room_id, key) DO NOTHING",
            (room_id, key, value),
        )
    await conn.commit()


async def _arun_migration(conn: psycopg.AsyncConnection[Row]) -> None:
    sql = _migration_path.read_text()
    for statement in sql.split(";"):
        stmt = statement.strip()
        if stmt:
            await conn.execute(pgsql.SQL(cast("LiteralString", stmt)))
    await conn.commit()


async def init_db(db_url: str | None = None) -> None:
    global _pool  # noqa: PLW0603
    url = db_url or settings.database_url
    # Cast: psycopg stubs don't expose overloads for dict_row row_factory
    conn = cast(
        "psycopg.AsyncConnection[Row]", await psycopg.AsyncConnection.connect(url)
    )
    async with conn:
        await _arun_migration(conn)
        await _aseed(conn)
    pool = cast(
        "AsyncConnectionPool[psycopg.AsyncConnection[Row]]",
        AsyncConnectionPool(
            url,
            min_size=settings.db_pool_min,
            max_size=settings.db_pool_max,
            kwargs={"row_factory": dict_row, "autocommit": False},
            open=False,
        ),
    )
    await pool.open()
    _pool = pool


def _get_pool() -> AsyncConnectionPool[psycopg.AsyncConnection[Row]]:
    if _pool is None:
        msg = "Database not initialized -- call init_db() first"
        raise RuntimeError(msg)
    return _pool


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[psycopg.AsyncConnection[Any], None]:
    # FastAPI deduplicates Depends(get_db) per request -- only one connection
    # is acquired even when multiple dependencies share Depends(get_db).
    if _test_conn is not None:
        yield _test_conn
        return
    t_acquire = time.perf_counter()
    t_yield = t_acquire
    async with _get_pool().connection() as conn:
        t_yield = time.perf_counter()
        acquire_ms = (t_yield - t_acquire) * 1000
        if acquire_ms > _ACQUIRE_WARN_MS:
            logger.warning(
                "DB connection acquire took %.1fms (pool may be exhausted)",
                acquire_ms,
            )
        yield conn
    hold_ms = (time.perf_counter() - t_yield) * 1000
    logger.debug("DB connection held for %.1fms (acquire=%.1fms)", hold_ms, acquire_ms)


@contextlib.asynccontextmanager
async def get_db_context() -> AsyncGenerator[psycopg.AsyncConnection[Any], None]:
    """
    Get a DB connection as an async context manager (not a FastAPI dependency).

    Use this when you need brief DB access outside of request DI lifecycle,
    e.g. SSE endpoints that must release the connection before streaming.
    """
    if _test_conn is not None:
        yield _test_conn
        return
    async with _get_pool().connection() as conn:
        yield conn


async def mark_user_active(user_id: str) -> None:
    async with _get_pool().connection() as conn:
        await conn.execute(
            "UPDATE users SET is_active = TRUE WHERE id = %s",
            (user_id,),
        )
        await conn.commit()


async def mark_user_inactive(user_id: str) -> None:
    async with _get_pool().connection() as conn:
        await conn.execute(
            "UPDATE users SET is_active = FALSE WHERE id = %s",
            (user_id,),
        )
        await conn.commit()


async def reset_db(db_url: str) -> None:
    """Reset the pool to a new URL (used in tests)."""
    global _pool  # noqa: PLW0603
    if _pool is not None:
        await _pool.close()
    conn = cast(
        "psycopg.AsyncConnection[Row]", await psycopg.AsyncConnection.connect(db_url)
    )
    async with conn:
        await _arun_migration(conn)
    pool = cast(
        "AsyncConnectionPool[psycopg.AsyncConnection[Row]]",
        AsyncConnectionPool(
            db_url,
            min_size=2,
            max_size=10,
            kwargs={"row_factory": dict_row, "autocommit": False},
            open=False,
        ),
    )
    await pool.open()
    _pool = pool
