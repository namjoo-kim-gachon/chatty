"""drop users.last_room_id column

Revision ID: 003_drop_user_last_room_id
Revises: 002_drop_message_edit_cols
Create Date: 2026-04-09

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "003_drop_user_last_room_id"
down_revision: Union[str, Sequence[str], None] = "002_drop_message_edit_cols"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS last_room_id")


def downgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_room_id TEXT")
