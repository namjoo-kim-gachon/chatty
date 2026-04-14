from __future__ import annotations

import re

from app.database import DBConn


def _matches(text: str, pattern: str, pattern_type: str) -> bool:
    if pattern_type == "regex":
        try:
            return bool(re.search(pattern, text, re.IGNORECASE))
        except re.error:
            return False
    # keyword (default)
    return pattern.lower() in text.lower()


async def check_global_filters(text: str, db: DBConn) -> bool:
    """Check whether text is blocked by a global filter."""
    cur = await db.execute("SELECT pattern, pattern_type FROM global_filters")
    filters = await cur.fetchall()
    for f in filters:
        if _matches(text, str(f["pattern"]), str(f["pattern_type"])):
            return True
    return False


async def check_room_filters(text: str, room_id: str, db: DBConn) -> bool:
    """Check whether text is blocked by a room filter."""
    cur = await db.execute(
        "SELECT pattern, pattern_type FROM room_filters WHERE room_id = %s", (room_id,)
    )
    filters = await cur.fetchall()
    for f in filters:
        if _matches(text, str(f["pattern"]), str(f["pattern_type"])):
            return True
    return False
