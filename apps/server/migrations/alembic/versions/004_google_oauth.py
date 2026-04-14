"""google_oauth: replace password auth with Google OAuth

Revision ID: 004_google_oauth
Revises: 003_drop_user_last_room_id
Create Date: 2026-04-14

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "004_google_oauth"
down_revision: Union[str, Sequence[str], None] = "003_drop_user_last_room_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS password_hash")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id TEXT")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id"
        " ON users(google_id) WHERE google_id IS NOT NULL"
    )
    op.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id         TEXT PRIMARY KEY,
            user_id    TEXT NOT NULL,
            expires_at DOUBLE PRECISION NOT NULL,
            created_at DOUBLE PRECISION NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS refresh_tokens")
    op.execute("DROP INDEX IF EXISTS idx_users_google_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS google_id")
    op.execute(
        "ALTER TABLE users"
        " ADD COLUMN IF NOT EXISTS password_hash TEXT NOT NULL DEFAULT ''"
    )
