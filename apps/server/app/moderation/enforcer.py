from __future__ import annotations

import re
import time

from fastapi import HTTPException, status

from app.moderation import cache as mod_cache
from app.moderation.spam import spam_detector


def _matches(text: str, pattern: str, pattern_type: str) -> bool:
    if pattern_type == "regex":
        try:
            return bool(re.search(pattern, text, re.IGNORECASE))
        except re.error:
            return False
    return pattern.lower() in text.lower()


async def run_pipeline(  # noqa: C901
    text: str,
    room_id: str,
    user_id: str,
) -> None:
    """Run the 7-step moderation pipeline. Raises HTTPException on violation."""
    now = time.time()

    # Steps 1-3: Check global ban, room ban, room mute
    # (cache-first, 0 DB queries on hit)
    globally_banned, room_banned, room_muted = await mod_cache.check_moderation(
        user_id, room_id
    )
    if globally_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are globally banned",
        )
    if room_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are banned from this room",
        )
    if room_muted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are muted in this room",
        )

    # 4. Slow mode (cache-first)
    room_meta = await mod_cache.get_room(room_id)
    if room_meta is not None:
        slow = room_meta.slow_mode_sec
        if slow > 0:
            last_at = await mod_cache.get_last_msg_at(room_id, user_id)
            if last_at is not None:
                elapsed = now - last_at
                if elapsed < slow:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Slow mode: wait {slow - elapsed:.1f}s",
                    )

    # 5-6. Global + room filters (cache-first, 0 DB queries on hit)
    filters = await mod_cache.get_filters(room_id)
    for f in filters:
        if _matches(text, f.pattern, f.pattern_type):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Message blocked by filter",
            )

    # 7. Spam detection (in-memory checks + DB for auto-mute)
    if await spam_detector.check(text, room_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Spam detected, you have been muted",
        )
