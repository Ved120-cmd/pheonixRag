"""Add embedding job and metadata tables.

Revision ID: 007_add_embeddings
Revises: 006_add_chunking
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007_add_embeddings"
down_revision: Union[str, None] = "006_add_chunking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "embedding_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("configuration_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_version", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("total_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("processing_duration", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, table, column in [
        ("ix_embedding_jobs_document_id", "embedding_jobs", "document_id"),
        ("ix_embedding_jobs_configuration_fingerprint", "embedding_jobs", "configuration_fingerprint"),
        ("ix_embedding_jobs_status", "embedding_jobs", "status"),
    ]:
        op.create_index(name, table, [column])

    op.create_table(
        "chunk_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("chunk_content_hash", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_version", sa.String(length=255), nullable=False),
        sa.Column("configuration_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("normalized", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("processing_duration", sa.Float(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chunk_id", "model_name", "model_version", "configuration_fingerprint",
            name="uq_chunk_embedding_configuration",
        ),
    )
    for name, column in [
        ("ix_chunk_embeddings_chunk_id", "chunk_id"),
        ("ix_chunk_embeddings_document_id", "document_id"),
        ("ix_chunk_embeddings_document_version", "document_version"),
        ("ix_chunk_embeddings_configuration_fingerprint", "configuration_fingerprint"),
        ("ix_chunk_embeddings_status", "status"),
    ]:
        op.create_index(name, "chunk_embeddings", [column])


def downgrade() -> None:
    for name in [
        "ix_chunk_embeddings_status",
        "ix_chunk_embeddings_configuration_fingerprint",
        "ix_chunk_embeddings_document_version",
        "ix_chunk_embeddings_document_id",
        "ix_chunk_embeddings_chunk_id",
    ]:
        op.drop_index(name, table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")
    for name in [
        "ix_embedding_jobs_status",
        "ix_embedding_jobs_configuration_fingerprint",
        "ix_embedding_jobs_document_id",
    ]:
        op.drop_index(name, table_name="embedding_jobs")
    op.drop_table("embedding_jobs")