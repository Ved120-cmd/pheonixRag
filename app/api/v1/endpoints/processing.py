from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from uuid import UUID

from app.api.dependencies.services import get_processing_service
from app.application.services.processing_service import ProcessingService

router = APIRouter()


class EnqueueReq(BaseModel):
    document_id: UUID


@router.post("", status_code=201)
async def enqueue(req: EnqueueReq, svc: ProcessingService = Depends(get_processing_service)):
    job = await svc.process_document(req.document_id)
    if job.status in ("failed", "error"):
        raise HTTPException(status_code=500, detail={"status": job.status, "error": job.last_error})
    return {
        "id": str(job.id),
        "document_id": str(job.document_id),
        "status": job.status,
        "parser": job.parser,
        "pages": job.pages,
        "char_count": job.char_count,
        "word_count": job.word_count,
        "processing_duration": job.processing_duration,
        "structured_result": job.structured_result,
    }


@router.get("/{job_id}")
async def get_job(job_id: UUID, svc: ProcessingService = Depends(get_processing_service)):
    job = await svc._processing_repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404)
    return {
        "id": str(job.id),
        "document_id": str(job.document_id),
        "status": job.status,
        "parser": job.parser,
        "pages": job.pages,
        "char_count": job.char_count,
        "word_count": job.word_count,
        "processing_duration": job.processing_duration,
        "structured_result": job.structured_result,
        "logs": job.logs,
    }


@router.get("/document/{document_id}")
async def list_by_document(document_id: UUID, svc: ProcessingService = Depends(get_processing_service)):
    jobs = await svc._processing_repo.list_by_document(document_id)
    return [
        {
            "id": str(j.id),
            "status": j.status,
            "parser": j.parser,
            "pages": j.pages,
            "char_count": j.char_count,
            "word_count": j.word_count,
            "processing_duration": j.processing_duration,
        }
        for j in jobs
    ]
