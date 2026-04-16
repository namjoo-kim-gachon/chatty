"""lobby_admin_only: set admin_only attr on lobby room

Revision ID: 005_lobby_admin_only
Revises: 004_google_oauth
Create Date: 2026-04-15

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "005_lobby_admin_only"
down_revision: Union[str, Sequence[str], None] = "004_google_oauth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO room_attrs (room_id, key, value)
        VALUES ('lobby', 'admin_only', 'true')
        ON CONFLICT (room_id, key) DO UPDATE SET value = 'true'
    """)


def downgrade() -> None:
    op.execute(
        "DELETE FROM room_attrs WHERE room_id = 'lobby' AND key = 'admin_only'"
    )
