from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.infrastructure.database.session import get_db_session
from app.application.services.chunking_service import ChunkingService
from app.domain.entities.chunk import ChunkingConfig
from app.domain.entities.user import User
from app.infrastructure.database.repositories.chunk_repository import SQLAlchemyChunkRepository
from app.infrastructure.database.repositories.chunking_run_repository import SQLAlchemyChunkingRunRepository
from app.infrastructure.database.repositories.document_repository import SQLAlchemyDocumentRepository
from app.infrastructure.database.repositories.processing_repository import SQLAlchemyProcessingRepository

router = APIRouter()


class ChunkingConfigRequest(BaseModel):
    strategy: str = "recursive"
    chunk_size: int = Field(1000, gt=0)
    overlap: int = Field(100, ge=0)
    minimum_chunk_size: int = Field(100, ge=0)
    maximum_chunk_size: int = Field(1500, gt=0)
    similarity_threshold: float = Field(0.75, ge=0, le=1)
    parent_size: int = Field(2000, gt=0)
    child_size: int = Field(500, gt=0)

    def to_domain(self) -> ChunkingConfig:
        return ChunkingConfig(**self.model_dump())


def get_chunking_service(session: AsyncSession = Depends(get_db_session)) -> ChunkingService:
    return ChunkingService(
        SQLAlchemyChunkRepository(session),
        SQLAlchemyChunkingRunRepository(session),
        SQLAlchemyDocumentRepository(session),
        SQLAlchemyProcessingRepository(session),
    )


async def _owned(document_id: UUID, user: User, service: ChunkingService) -> None:
    document = await service._documents.get_by_id(document_id)
    if document is None or document.owner_id != user.id:
        raise HTTPException(status_code=404, detail="document not found")


@router.post("/documents/{document_id}/chunking")
async def start_chunking(
    document_id: UUID,
    config: ChunkingConfigRequest,
    user: User = Depends(get_current_user),
    service: ChunkingService = Depends(get_chunking_service),
):
    await _owned(document_id, user, service)
    try:
        return await service.run(document_id, config.to_domain())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/documents/{document_id}/chunking/rechunk")
async def rechunk_document(
    document_id: UUID,
    config: ChunkingConfigRequest,
    user: User = Depends(get_current_user),
    service: ChunkingService = Depends(get_chunking_service),
):
    await _owned(document_id, user, service)
    return await service.retry(document_id, config.to_domain())


@router.put("/documents/{document_id}/chunking/configuration")
async def change_configuration(
    document_id: UUID,
    config: ChunkingConfigRequest,
    user: User = Depends(get_current_user),
    service: ChunkingService = Depends(get_chunking_service),
):
    await _owned(document_id, user, service)
    return await service.run(document_id, config.to_domain(), force=True)


@router.get("/documents/{document_id}/chunking/status")
async def chunking_status(
    document_id: UUID,
    user: User = Depends(get_current_user),
    service: ChunkingService = Depends(get_chunking_service),
):
    await _owned(document_id, user, service)
    run = await service.status(document_id)
    if run is None:
        raise HTTPException(status_code=404, detail="chunking run not found")
    return run


@router.get("/documents/{document_id}/chunks")
async def list_chunks(
    document_id: UUID,
    user: User = Depends(get_current_user),
    service: ChunkingService = Depends(get_chunking_service),
):
    await _owned(document_id, user, service)
    return await service.list_chunks(document_id)


@router.get("/documents/{document_id}/chunks/statistics")
async def chunk_statistics(
    document_id: UUID,
    user: User = Depends(get_current_user),
    service: ChunkingService = Depends(get_chunking_service),
):
    await _owned(document_id, user, service)
    run = await service.status(document_id)
    if run is None:
        raise HTTPException(status_code=404, detail="chunking run not found")
    return run.statistics
