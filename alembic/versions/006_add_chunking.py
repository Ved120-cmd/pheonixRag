"""Add chunking runs and document chunks.

Revision ID: 006_add_chunking
Revises: 005_add_processing_jobs
Create Date: 2026-09-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006_add_chunking"
down_revision: Union[str, None] = "005_add_processing_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chunking_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("strategy", sa.String(length=64), nullable=False),
        sa.Column("configuration", sa.Text(), nullable=False),
        sa.Column("statistics", sa.Text(), nullable=True),
        sa.Column("warnings", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chunking_runs_document_id", "chunking_runs", ["document_id"])
    op.create_index("ix_chunking_runs_status", "chunking_runs", ["status"])
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("page_numbers", sa.Text(), nullable=True),
        sa.Column("section_path", sa.Text(), nullable=True),
        sa.Column("document_metadata", sa.Text(), nullable=True),
        sa.Column("strategy", sa.String(length=64), nullable=False),
        sa.Column("configuration", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, table, column in [
        ("ix_document_chunks_document_id", "document_chunks", "document_id"),
        ("ix_document_chunks_parent_chunk_id", "document_chunks", "parent_chunk_id"),
        ("ix_document_chunks_document_version", "document_chunks", "document_version"),
        ("ix_document_chunks_content_hash", "document_chunks", "content_hash"),
        ("ix_document_chunks_is_active", "document_chunks", "is_active"),
    ]:
        op.create_index(name, table, [column])


def downgrade() -> None:
    for name in ["ix_document_chunks_is_active", "ix_document_chunks_content_hash", "ix_document_chunks_document_version", "ix_document_chunks_parent_chunk_id", "ix_document_chunks_document_id"]:
        op.drop_index(name, table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_chunking_runs_status", table_name="chunking_runs")
    op.drop_index("ix_chunking_runs_document_id", table_name="chunking_runs")
    op.drop_table("chunking_runs")
