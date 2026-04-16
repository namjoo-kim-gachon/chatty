"""Drop global_bans table for privacy enhancement.

This migration removes the global_bans table as part of privacy enhancement:
- Global ban functionality is being removed
- Only room-level moderation (ban, mute) will be supported
- This aligns with privacy-first approach (no admin-level controls)

Revision ID: 007
Revises: 006_truncate_messages
Create Date: 2026-04-16
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "007_drop_global_bans"
down_revision = "006_truncate_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop global_bans table."""
    op.execute("DROP TABLE IF EXISTS global_bans CASCADE")


def downgrade() -> None:
    """No downgrade available - data is permanently deleted."""
    # Recreate global_bans table structure for rollback
    op.execute("""
        CREATE TABLE IF NOT EXISTS global_bans (
            id          TEXT PRIMARY KEY,
            user_id     TEXT UNIQUE NOT NULL,
            reason      TEXT NOT NULL DEFAULT '',
            banned_by   TEXT NOT NULL,
            created_at  DOUBLE PRECISION NOT NULL,
            expires_at  DOUBLE PRECISION,
            FOREIGN KEY (user_id)   REFERENCES users(id),
            FOREIGN KEY (banned_by) REFERENCES users(id)
        )
    """)
