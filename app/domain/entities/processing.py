from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class ProcessingJob:
    id: uuid.UUID
    document_id: uuid.UUID
    status: str
    parser: str | None
    attempt_count: int
    last_error: str | None
    pages: int | None
    char_count: int | None
    word_count: int | None
    processing_duration: float | None
    extraction_quality: float | None
    structured_result: dict | None
    logs: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


def new_processing_job(document_id: uuid.UUID) -> ProcessingJob:
    return ProcessingJob(
        id=uuid.uuid4(),
        document_id=document_id,
        status="queued",
        parser=None,
        attempt_count=0,
        last_error=None,
        pages=None,
        char_count=None,
        word_count=None,
        processing_duration=None,
        extraction_quality=None,
        structured_result=None,
        logs=None,
    )
