from __future__ import annotations

import re
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field

from app.database import get_db_context
from app.moderation import cache as mod_cache


@dataclass
class _UserHistory:
    texts: deque[tuple[float, str]] = field(default_factory=lambda: deque(maxlen=100))
    timestamps: deque[float] = field(default_factory=lambda: deque(maxlen=100))


class SpamDetector:
    def __init__(self) -> None:
        # (room_id, user_id) -> history
        self._history: dict[tuple[str, str], _UserHistory] = defaultdict(_UserHistory)

    async def check(
        self,
        text: str,
        room_id: str,
        user_id: str,
    ) -> bool:
        """Detect spam and apply auto-mute if triggered."""
        now = time.time()
        key = (room_id, user_id)
        hist = self._history[key]

        hist.timestamps.append(now)
        hist.texts.append((now, text))

        # Rule 1: same text 3+ times within 60s
        _DUPLICATE_THRESHOLD = 3  # noqa: N806
        cutoff_60 = now - 60
        recent_same = sum(1 for ts, t in hist.texts if ts >= cutoff_60 and t == text)
        if recent_same >= _DUPLICATE_THRESHOLD:
            await self._auto_mute(
                room_id, user_id, minutes=10, reason="spam: duplicate messages"
            )
            return True

        # Rule 2: 5+ messages within 5s
        _RATE_THRESHOLD = 5  # noqa: N806
        cutoff_5 = now - 5
        recent_5 = sum(1 for ts in hist.timestamps if ts >= cutoff_5)
        if recent_5 >= _RATE_THRESHOLD:
            await self._auto_mute(
                room_id, user_id, minutes=5, reason="spam: rate exceeded"
            )
            return True

        # Rule 3: 5+ URLs within 60s
        url_pattern = re.compile(r"https?://|www\.", re.IGNORECASE)
        if url_pattern.search(text):
            recent_urls = sum(
                1 for ts, t in hist.texts if ts >= cutoff_60 and url_pattern.search(t)
            )
            _URL_THRESHOLD = 5  # noqa: N806
            if recent_urls >= _URL_THRESHOLD:
                await self._auto_mute(
                    room_id, user_id, minutes=30, reason="spam: too many URLs"
                )
                return True

        return False

    async def _auto_mute(
        self,
        room_id: str,
        user_id: str,
        minutes: int,
        reason: str,
    ) -> None:
        now = time.time()
        expires_at = now + minutes * 60
        mute_id = str(uuid.uuid4())
        try:
            async with get_db_context() as db:
                await db.execute(
                    """
                    INSERT INTO room_mutes
                        (id, room_id, user_id, reason, muted_by, created_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (room_id, user_id) DO UPDATE
                        SET id = EXCLUDED.id,
                            reason = EXCLUDED.reason,
                            created_at = EXCLUDED.created_at,
                            expires_at = EXCLUDED.expires_at
                    """,
                    (mute_id, room_id, user_id, reason, user_id, now, expires_at),
                )
                await db.commit()
            await mod_cache.set_muted(room_id, user_id, expires_at)
        except Exception:  # noqa: BLE001, S110
            pass


spam_detector = SpamDetector()
