"""Truncate messages table for privacy.

This migration truncates all existing messages as part of the privacy enhancement:
- Messages will no longer be persisted to database
- Only Redis ring buffer will store recent messages (last 200 per room)
- This ensures better privacy and data minimization

Revision ID: 006
Revises:
Create Date: 2026-04-16
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "006_truncate_messages"
down_revision = "005_lobby_admin_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Truncate messages table to delete all existing message data."""
    op.execute("TRUNCATE TABLE messages RESTART IDENTITY CASCADE")


def downgrade() -> None:
    """No downgrade available - data is permanently deleted."""
    pass
