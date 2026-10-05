from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Uuid, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class IndexingJobModel(Base):
    __tablename__ = "indexing_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_indexing_job_idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_version: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_set_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    collection_name: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    total_vectors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_vectors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_vectors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DocumentIndexStateModel(Base):
    __tablename__ = "document_index_states"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    active_document_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_chunk_set_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active_collection: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active_embedding_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)