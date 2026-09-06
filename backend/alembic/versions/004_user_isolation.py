"""004 add user_id to ai_agents and office_rooms for multi-user isolation

Revision ID: 004_user_isolation
Revises: 43d180772dbc
Create Date: 2026-09-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_user_isolation'
down_revision: Union[str, Sequence[str], None] = '43d180772dbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user_id foreign key to ai_agents and office_rooms."""
    # Add user_id to ai_agents
    op.add_column('ai_agents', sa.Column('user_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_ai_agents_user_id', 'ai_agents', 'users', ['user_id'], ['id'])
    op.create_index('ix_ai_agents_user_id', 'ai_agents', ['user_id'])

    # Add user_id to office_rooms
    op.add_column('office_rooms', sa.Column('user_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_office_rooms_user_id', 'office_rooms', 'users', ['user_id'], ['id'])
    op.create_index('ix_office_rooms_user_id', 'office_rooms', ['user_id'])


def downgrade() -> None:
    """Remove user_id from ai_agents and office_rooms."""
    op.drop_index('ix_office_rooms_user_id', table_name='office_rooms')
    op.drop_constraint('fk_office_rooms_user_id', 'office_rooms', type_='foreignkey')
    op.drop_column('office_rooms', 'user_id')

    op.drop_index('ix_ai_agents_user_id', table_name='ai_agents')
    op.drop_constraint('fk_ai_agents_user_id', 'ai_agents', type_='foreignkey')
    op.drop_column('ai_agents', 'user_id')
