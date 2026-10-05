from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.application.embeddings.registry import EmbeddingProviderRegistry
from app.application.services.embedding_service import EmbeddingService
from app.config.settings import get_settings
from app.domain.entities.embedding import EmbeddingConfig
from app.domain.entities.user import User
from app.infrastructure.database.repositories.chunk_repository import SQLAlchemyChunkRepository
from app.infrastructure.database.repositories.embedding_repository import SQLAlchemyEmbeddingRepository
from app.infrastructure.database.session import get_db_session
from app.infrastructure.embedding.sentence_transformer import SentenceTransformerEmbeddingProvider
from app.application.tasks.embed_document import embed_document_task

router = APIRouter(prefix="/embeddings", tags=["embeddings"])
settings = get_settings()
registry = EmbeddingProviderRegistry(SentenceTransformerEmbeddingProvider)


def _config() -> EmbeddingConfig:
    return EmbeddingConfig(
        model_name=settings.embedding_model_name,
        model_version=settings.embedding_model_version,
        dimension=settings.embedding_dimension,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        normalize=settings.embedding_normalize,
        max_input_tokens=settings.embedding_max_input_tokens,
    )


def get_embedding_service(session: AsyncSession = Depends(get_db_session)) -> EmbeddingService:
    return EmbeddingService(SQLAlchemyChunkRepository(session), SQLAlchemyEmbeddingRepository(session), registry, _config())


class EmbeddingConfigRequest(BaseModel):
    model_name: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    dimension: int = Field(gt=0)
    device: str = "auto"
    batch_size: int = Field(gt=0)
    normalize: bool = True
    max_input_tokens: int = Field(gt=0)

    def to_domain(self) -> EmbeddingConfig:
        return EmbeddingConfig(**self.model_dump())


def _job_response(job):
    return {
        "id": str(job.id),
        "document_id": str(job.document_id),
        "document_version": job.document_version,
        "model_name": job.model_name,
        "model_version": job.model_version,
        "status": job.status,
        "total_chunks": job.total_chunks,
        "completed_chunks": job.completed_chunks,
        "failed_chunks": job.failed_chunks,
        "progress_percent": job.progress_percent,
        "retry_count": job.retry_count,
        "error": job.error,
        "processing_duration": job.processing_duration,
    }


@router.post("/documents/{document_id}")
async def start_embedding(
    document_id: UUID,
    force: bool = False,
    _: User = Depends(get_current_user),
    service: EmbeddingService = Depends(get_embedding_service),
):
    try:
        job = await service.create_job(document_id, force=force)
        if job.status == "queued":
            embed_document_task.delay(str(job.id))
        return _job_response(job)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/documents/{document_id}/retry")
async def retry_embedding(
    document_id: UUID,
    _: User = Depends(get_current_user),
    service: EmbeddingService = Depends(get_embedding_service),
):
    try:
        job = await service.create_job(document_id, force=True)
        embed_document_task.delay(str(job.id))
        return _job_response(job)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs/{job_id}")
async def embedding_job_status(
    job_id: UUID,
    _: User = Depends(get_current_user),
    service: EmbeddingService = Depends(get_embedding_service),
):
    job = await service.status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="embedding job not found")
    return _job_response(job)


@router.get("/documents/{document_id}/status")
async def document_embedding_status(
    document_id: UUID,
    _: User = Depends(get_current_user),
    service: EmbeddingService = Depends(get_embedding_service),
):
    try:
        result = await service.document_status(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result["job"] = _job_response(result["job"])
    return result


@router.get("/statistics")
async def embedding_statistics(
    _: User = Depends(get_current_user),
    service: EmbeddingService = Depends(get_embedding_service),
):
    return await service.statistics()


@router.get("/configuration")
async def embedding_configuration(_: User = Depends(get_current_user)):
    return _config().as_dict()


@router.put("/configuration")
async def update_embedding_configuration(
    request: EmbeddingConfigRequest,
    _: User = Depends(get_current_user),
):
    config = request.to_domain()
    settings.embedding_model_name = config.model_name
    settings.embedding_model_version = config.model_version
    settings.embedding_dimension = config.dimension
    settings.embedding_device = config.device
    settings.embedding_batch_size = config.batch_size
    settings.embedding_normalize = config.normalize
    settings.embedding_max_input_tokens = config.max_input_tokens
    registry.invalidate()
    return config.as_dict()