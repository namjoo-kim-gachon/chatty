"""drop message edited_at and deleted_at columns

Revision ID: 002_drop_message_edit_cols
Revises: 001_initial
Create Date: 2026-04-09

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "002_drop_message_edit_cols"
down_revision: Union[str, Sequence[str], None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE messages DROP COLUMN IF EXISTS edited_at,"
        " DROP COLUMN IF EXISTS deleted_at"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE messages"
        " ADD COLUMN IF NOT EXISTS edited_at DOUBLE PRECISION,"
        " ADD COLUMN IF NOT EXISTS deleted_at DOUBLE PRECISION"
    )
