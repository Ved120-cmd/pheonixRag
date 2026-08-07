import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Uuid, func, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class DocumentModel(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    meta_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
