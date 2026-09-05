from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.chunking_run import ChunkingRun
from app.infrastructure.database.mappers import chunking_run_to_entity, chunking_run_to_model
from app.infrastructure.database.models.chunking_run import ChunkingRunModel


class SQLAlchemyChunkingRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, run: ChunkingRun) -> ChunkingRun:
        model = chunking_run_to_model(run)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return chunking_run_to_entity(model)

    async def update(self, run: ChunkingRun) -> ChunkingRun:
        result = await self._session.execute(select(ChunkingRunModel).where(ChunkingRunModel.id == run.id))
        model = result.scalar_one()
        model.status = run.status
        model.statistics = chunking_run_to_model(run).statistics
        model.warnings = chunking_run_to_model(run).warnings
        model.error = run.error
        model.attempts = run.attempts
        await self._session.commit()
        await self._session.refresh(model)
        return chunking_run_to_entity(model)

    async def get(self, run_id: UUID) -> ChunkingRun | None:
        result = await self._session.execute(select(ChunkingRunModel).where(ChunkingRunModel.id == run_id))
        model = result.scalar_one_or_none()
        return chunking_run_to_entity(model) if model else None

    async def latest(self, document_id: UUID) -> ChunkingRun | None:
        result = await self._session.execute(
            select(ChunkingRunModel)
            .where(ChunkingRunModel.document_id == document_id)
            .order_by(ChunkingRunModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return chunking_run_to_entity(model) if model else None
