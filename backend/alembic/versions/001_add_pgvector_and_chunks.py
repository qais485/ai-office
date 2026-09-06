"""Add pgvector extension and knowledge_chunks table

Revision ID: 001
Revises: 000
Create Date: 2026-08-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = '001'
down_revision: Union[str, None] = '000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create knowledge_chunks table
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('knowledge_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('knowledge_sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_knowledge_chunks_knowledge_id', 'knowledge_chunks', ['knowledge_id'])

    # IVFFlat index for vector similarity search
    # NOTE: IVFFlat requires at least N rows to build lists. With <1000 rows
    # we use lists=10 (100 rows per list minimum). After bulk ingestion,
    # run: REINDEX INDEX ix_knowledge_chunks_embedding;
    # For small datasets we fall back to a sequential scan anyway.
    op.execute("""
        CREATE INDEX ix_knowledge_chunks_embedding
        ON knowledge_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 10)
    """)

    # Add embedding_dimensions column to knowledge_sources for tracking
    op.add_column('knowledge_sources', sa.Column('embedding_dimensions', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_table('knowledge_chunks')
    op.execute("DROP EXTENSION IF EXISTS vector")
