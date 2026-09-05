"""rename documents.metadata to meta_payload

Revision ID: 004_rename_meta_payload
Revises: 003_add_documents
Create Date: 2026-08-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "004_rename_meta_payload"
down_revision = "003_add_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "documents",
        "metadata",
        new_column_name="meta_payload",
        existing_type=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "documents",
        "meta_payload",
        new_column_name="metadata",
        existing_type=sa.Text(),
        existing_nullable=True,
    )