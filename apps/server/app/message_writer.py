from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Any, cast

import psycopg

from app.redis_client import get_redis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Write job
# ---------------------------------------------------------------------------


@dataclass
class WriteJob:
    msg_id: str
    room_id: str
    user_id: str
    nickname: str
    text: str
    msg_type: str
    seq: int
    created_at: float


# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

_write_queue: queue.Queue[WriteJob | None] = queue.Queue()
_thread: threading.Thread | None = None

# When set, enqueue() writes synchronously to this DB URL instead of the queue.
# Intended for test environments only.
_test_db_url: str | None = None


# ---------------------------------------------------------------------------
# Seq helpers  (async -- backed by Redis INCR)
# ---------------------------------------------------------------------------


async def next_seq(room_id: str) -> int:
    """Atomically advance and return the next seq for *room_id*."""
    return int(await get_redis().incr(f"chatty:seq:{room_id}"))


async def current_seq(room_id: str) -> int:
    """Return the most-recently assigned seq for *room_id* (0 if none)."""
    val = await get_redis().get(f"chatty:seq:{room_id}")
    return int(val) if val is not None else 0


# ---------------------------------------------------------------------------
# Queue interface  (thread-safe -- can be called from any thread)
# ---------------------------------------------------------------------------


def enqueue(job: WriteJob) -> None:
    """
    Put a write job on the queue. Non-blocking, thread-safe.

    In test mode (_test_db_url is set), writes synchronously to the test DB
    so that queries issued in the same test see the committed rows immediately.
    """
    if _test_db_url is not None:
        _write_sync(job, _test_db_url)
        return
    _write_queue.put_nowait(job)


def _write_sync(job: WriteJob, db_url: str) -> None:
    """Write a single job synchronously. Test use only."""
    with cast("Any", psycopg.connect(db_url, autocommit=False)) as conn:
        conn.execute(
            "INSERT INTO messages"
            " (id, room_id, user_id, nickname, text, msg_type, seq, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT DO NOTHING",
            (
                job.msg_id,
                job.room_id,
                job.user_id,
                job.nickname,
                job.text,
                job.msg_type,
                job.seq,
                job.created_at,
            ),
        )
        conn.execute(
            "INSERT INTO room_seq (room_id, seq) VALUES (%s, %s)"
            " ON CONFLICT (room_id)"
            " DO UPDATE SET seq = GREATEST(room_seq.seq, EXCLUDED.seq)",
            (job.room_id, job.seq),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Writer thread
# ---------------------------------------------------------------------------


def _writer_loop(db_url: str) -> None:
    """Run in a dedicated thread. Drain the queue in batches."""
    with cast("Any", psycopg.connect(db_url, autocommit=False)) as conn:
        while True:
            # Block until the first item arrives (or shutdown sentinel).
            job = _write_queue.get()
            if job is None:
                _write_queue.task_done()
                return

            # Drain any additional items that are already queued -- batch them
            # into a single INSERT to reduce round-trips.
            batch: list[WriteJob] = [job]
            try:
                while True:
                    item = _write_queue.get_nowait()
                    if item is None:
                        # Shutdown sentinel encountered mid-drain.
                        # Put it back so the outer loop handles it cleanly.
                        _write_queue.put(None)
                        break
                    batch.append(item)
            except queue.Empty:
                pass

            try:
                conn.executemany(
                    """
                    INSERT INTO messages
                      (id, room_id, user_id, nickname, text, msg_type, seq, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            j.msg_id,
                            j.room_id,
                            j.user_id,
                            j.nickname,
                            j.text,
                            j.msg_type,
                            j.seq,
                            j.created_at,
                        )
                        for j in batch
                    ],
                )
                # Keep room_seq table in sync so restarts can recover seq state.
                room_max: dict[str, int] = {}
                for j in batch:
                    room_max[j.room_id] = max(room_max.get(j.room_id, 0), j.seq)
                for rid, max_seq in room_max.items():
                    conn.execute(
                        "INSERT INTO room_seq (room_id, seq) VALUES (%s, %s)"
                        " ON CONFLICT (room_id)"
                        " DO UPDATE SET seq = GREATEST(room_seq.seq, EXCLUDED.seq)",
                        (rid, max_seq),
                    )
                conn.commit()
                logger.debug("message_writer: wrote batch of %d", len(batch))
            except Exception:
                logger.exception("message_writer: batch failed, rolling back")
                conn.rollback()
            finally:
                for _ in batch:
                    _write_queue.task_done()


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


async def init_seqs(rows: list[dict[str, object]]) -> None:
    """
    Seed Redis seq counters from DB rows on startup.

    Uses SET NX so existing Redis values (in-flight increments) are preserved.
    Expects rows with ``room_id`` and ``seq`` keys, e.g. from::

        SELECT room_id, seq FROM room_seq
    """
    r = get_redis()
    pipe = r.pipeline()
    for row in rows:
        pipe.set(f"chatty:seq:{row['room_id']}", str(row["seq"]), nx=True)
    await pipe.execute()
    logger.debug("message_writer: seeded seqs for %d rooms", len(rows))


def start(db_url: str) -> None:
    """Start the background writer thread."""
    global _thread  # noqa: PLW0603
    _thread = threading.Thread(
        target=_writer_loop,
        args=(db_url,),
        daemon=True,
        name="message-writer",
    )
    _thread.start()
    logger.info("message_writer: started")


def stop() -> None:
    """Drain the queue and stop the writer thread (graceful shutdown)."""
    global _thread  # noqa: PLW0603
    if _thread is None:
        return
    _write_queue.join()  # wait for all enqueued jobs to finish
    _write_queue.put(None)  # send shutdown sentinel
    _thread.join()
    _thread = None
    logger.info("message_writer: stopped")
