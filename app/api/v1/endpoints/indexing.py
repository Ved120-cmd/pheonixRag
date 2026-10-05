from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.authorization import RequireRole
from app.api.dependencies.services import get_indexing_service
from app.application.services.indexing_service import IndexingService
from app.domain.entities.user import User
from app.application.tasks.index_document import index_document_task

router = APIRouter(prefix="/indexing", tags=["indexing"])


def _job_response(job):
    return {
        "id": str(job.id),
        "tenant_id": str(job.tenant_id),
        "document_id": str(job.document_id),
        "document_version": job.document_version,
        "collection": job.collection_name,
        "model_name": job.model_name,
        "model_version": job.model_version,
        "status": job.status,
        "total_vectors": job.total_vectors,
        "processed_vectors": job.processed_vectors,
        "failed_vectors": job.failed_vectors,
        "progress_percent": job.progress_percent,
        "retries": job.retries,
        "duration_seconds": job.duration_seconds,
        "error": job.error,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def _enqueue(job_id: UUID) -> None:
    try:
        index_document_task.apply_async(args=[str(job_id)], task_id=str(job_id))
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"message": "indexing queue is unavailable", "job_id": str(job_id)},
        ) from exc


@router.post("/documents/{document_id}", status_code=202)
async def start_indexing(
    document_id: UUID,
    user: User = Depends(get_current_user),
    service: IndexingService = Depends(get_indexing_service),
):
    try:
        job = await service.create_job(user.id, document_id)
        if job.status != "indexed":
            _enqueue(job.id)
        return _job_response(job)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/documents/{document_id}/reindex", status_code=202)
async def reindex_document(
    document_id: UUID,
    user: User = Depends(get_current_user),
    service: IndexingService = Depends(get_indexing_service),
):
    try:
        job = await service.create_job(user.id, document_id, force=True)
        _enqueue(job.id)
        return _job_response(job)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}")
async def get_indexing_job(
    job_id: UUID,
    user: User = Depends(get_current_user),
    service: IndexingService = Depends(get_indexing_service),
):
    job = await service.status(user.id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="indexing job not found")
    return _job_response(job)


@router.post("/jobs/{job_id}/retry", status_code=202)
async def retry_indexing_job(
    job_id: UUID,
    user: User = Depends(get_current_user),
    service: IndexingService = Depends(get_indexing_service),
):
    job = await service.status(user.id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="indexing job not found")
    try:
        retry_job = await service.retry_job(user.id, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _enqueue(retry_job.id)
    return _job_response(retry_job)


@router.post("/jobs/{job_id}/cancel")
async def cancel_indexing_job(
    job_id: UUID,
    user: User = Depends(get_current_user),
    service: IndexingService = Depends(get_indexing_service),
):
    try:
        job = await service.cancel_job(user.id, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _job_response(job)


@router.get("/documents/{document_id}/status")
async def document_indexing_status(
    document_id: UUID,
    user: User = Depends(get_current_user),
    service: IndexingService = Depends(get_indexing_service),
):
    try:
        result = await service.document_status(user.id, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "active_version": result["state"].active_document_version if result["state"] else None,
        "active_collection": result["state"].active_collection if result["state"] else None,
        "latest_job": _job_response(result["latest_job"]) if result["latest_job"] else None,
        "jobs": [_job_response(job) for job in result["jobs"]],
    }


@router.get("/documents/{document_id}/statistics")
async def document_indexing_statistics(
    document_id: UUID,
    user: User = Depends(get_current_user),
    service: IndexingService = Depends(get_indexing_service),
):
    try:
        result = await service.document_status(user.id, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    job = result["latest_job"]
    if job is None:
        return {"total_vectors": 0, "processed_vectors": 0, "failed_vectors": 0, "progress_percent": 0}
    return {
        "total_vectors": job.total_vectors,
        "processed_vectors": job.processed_vectors,
        "failed_vectors": job.failed_vectors,
        "progress_percent": job.progress_percent,
        "duration_seconds": job.duration_seconds,
        "status": job.status,
    }


@router.get("/statistics")
async def indexing_statistics(
    user: User = Depends(get_current_user),
    service: IndexingService = Depends(get_indexing_service),
):
    return await service.statistics(user.id)


@router.get("/collection")
async def collection_information(
    _: User = Depends(get_current_user),
    service: IndexingService = Depends(get_indexing_service),
):
    try:
        return await service.collection_info()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="vector collection unavailable") from exc


@router.delete("/documents/{document_id}/vectors")
async def delete_document_vectors(
    document_id: UUID,
    user: User = Depends(get_current_user),
    service: IndexingService = Depends(get_indexing_service),
):
    try:
        return await service.delete_document(user.id, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class RecreateCollectionRequest(BaseModel):
    confirm_data_loss: bool = False


@router.post("/collection/recreate")
async def recreate_collection(
    request: RecreateCollectionRequest,
    _: User = Depends(RequireRole("admin")),
    service: IndexingService = Depends(get_indexing_service),
):
    try:
        return await service.recreate_collection(request.confirm_data_loss)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
