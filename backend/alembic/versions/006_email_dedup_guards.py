"""006: anti-duplicate guards for email replies

- Deduplicate existing email_messages rows that were double-imported
  (same account_id + conversation_id), keeping the oldest row.
- Add unique index uq_email_messages_account_conversation so two workers can
  never insert the same source message twice.

Revision ID: a1f2c3d4e5f6
Revises: 88ef166063e4
Create Date: 2026-09-02 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '88ef166063e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    # 1. Remove duplicates first (keep the OLDEST row per identity pair).
    conn.execute(sa.text("""
        DELETE FROM email_messages a
        USING email_messages b
        WHERE a.conversation_id = b.conversation_id
          AND a.conversation_id IS NOT NULL
          AND COALESCE(a.account_id::text, '') = COALESCE(b.account_id::text, '')
          AND a.created_at > b.created_at
    """))

    # 2. Add the unique index (idempotent — safe if it already exists).
    conn.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_email_messages_account_conversation
        ON email_messages (account_id, conversation_id)
    """))


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    conn.execute(sa.text(
        "DROP INDEX IF EXISTS uq_email_messages_account_conversation"
    ))
