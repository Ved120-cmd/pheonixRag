"""Add durable vector indexing lifecycle state.

Revision ID: 008_add_vector_indexing
Revises: 007_add_embeddings
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_add_vector_indexing"
down_revision: Union[str, None] = "007_add_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "indexing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("chunk_set_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("collection_name", sa.String(length=255), nullable=False),
        sa.Column("embedding_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_version", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("total_vectors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_vectors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_vectors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_indexing_job_idempotency_key"),
    )
    op.create_index("ix_indexing_jobs_tenant_id", "indexing_jobs", ["tenant_id"])
    op.create_index("ix_indexing_jobs_document_id", "indexing_jobs", ["document_id"])
    op.create_index("ix_indexing_jobs_status", "indexing_jobs", ["status"])
    op.create_table(
        "document_index_states",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("active_document_version", sa.Integer(), nullable=True),
        sa.Column("active_chunk_set_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("active_collection", sa.String(length=255), nullable=True),
        sa.Column("active_embedding_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index("ix_document_index_states_tenant_id", "document_index_states", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_document_index_states_tenant_id", table_name="document_index_states")
    op.drop_table("document_index_states")
    op.drop_index("ix_indexing_jobs_status", table_name="indexing_jobs")
    op.drop_index("ix_indexing_jobs_document_id", table_name="indexing_jobs")
    op.drop_index("ix_indexing_jobs_tenant_id", table_name="indexing_jobs")
    op.drop_table("indexing_jobs")