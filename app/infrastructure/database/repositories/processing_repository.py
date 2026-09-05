from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.domain.entities.processing import ProcessingJob
from app.domain.repositories import processing_repository as processing_repo_iface
from app.infrastructure.database.mappers import processing_to_entity, processing_to_model
from app.infrastructure.database.models.processing import ProcessingModel


class SQLAlchemyProcessingRepository(processing_repo_iface.ProcessingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, job: ProcessingJob) -> ProcessingJob:
        model = processing_to_model(job)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return processing_to_entity(model)

    async def get_by_id(self, job_id):
        result = await self._session.execute(select(ProcessingModel).where(ProcessingModel.id == job_id))
        model = result.scalar_one_or_none()
        return processing_to_entity(model) if model else None

    async def update(self, job: ProcessingJob) -> ProcessingJob:
        result = await self._session.execute(select(ProcessingModel).where(ProcessingModel.id == job.id))
        model = result.scalar_one()
        model.status = job.status
        model.parser = job.parser
        model.attempt_count = job.attempt_count
        model.last_error = job.last_error
        model.pages = job.pages
        model.char_count = job.char_count
        model.word_count = job.word_count
        model.processing_duration = job.processing_duration
        model.extraction_quality = job.extraction_quality
        import json

        model.structured_result = json.dumps(job.structured_result) if job.structured_result else None
        model.logs = job.logs
        model.started_at = job.started_at
        model.completed_at = job.completed_at
        await self._session.commit()
        await self._session.refresh(model)
        return processing_to_entity(model)

    async def list_by_document(self, document_id):
        result = await self._session.execute(select(ProcessingModel).where(ProcessingModel.document_id == document_id).order_by(ProcessingModel.created_at.desc()))
        return [processing_to_entity(m) for m in result.scalars().all()]
