from __future__ import annotations

from app.infrastructure.tasks.celery_app import celery_app


@celery_app.task(bind=True)
def process_document(self, document_id: str) -> None:
    # placeholder: later phases will implement chunking/embedding/indexing
    # Mark processing steps and update document status via repo/service
    return None
