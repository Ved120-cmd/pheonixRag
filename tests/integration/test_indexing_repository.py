from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from app.domain.entities.indexing import DocumentIndexState, IndexingJob
from app.infrastructure.database.models.document import DocumentModel
from app.infrastructure.database.models.indexing import IndexingJobModel
from app.infrastructure.database.models.role import RoleModel
from app.infrastructure.database.models.user import UserModel
from app.infrastructure.database.models.chunk import ChunkModel
from app.infrastructure.database.repositories.indexing_repository import SQLAlchemyIndexingRepository


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sql_indexing_repository_is_idempotent_and_publishes_current_version(seeded_session):
    role_result = await seeded_session.execute(select(RoleModel).where(RoleModel.name == "user"))
    role = role_result.scalar_one()
    tenant_id = uuid.uuid4()
    document_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    document = DocumentModel(
        id=document_id,
        filename="test.pdf",
        mime_type="application/pdf",
        size=12,
        pages=1,
        owner_id=tenant_id,
        version=2,
        storage_path="tenant/test.pdf",
        checksum=uuid.uuid4().hex,
        status="processed",
        meta_payload=json.dumps({"tags": ["guide"]}),
    )
    user = UserModel(
        id=tenant_id,
        email=f"{tenant_id}@example.test",
        username=f"user-{tenant_id.hex[:12]}",
        hashed_password="not-used",
        role_id=role.id,
    )
    seeded_session.add_all([user, document])
    await seeded_session.flush()
    seeded_session.add(
        ChunkModel(
            id=chunk_id,
            document_id=document_id,
            document_version=2,
            chunk_index=0,
            text="version two chunk",
            token_count=3,
            character_count=18,
            page_numbers="[1]",
            section_path="[]",
            document_metadata="{}",
            strategy="recursive",
            configuration="{}",
            content_hash="a" * 64,
            is_active=True,
        )
    )
    await seeded_session.commit()

    repository = SQLAlchemyIndexingRepository(seeded_session)
    source = await repository.get_index_source(tenant_id, document_id)
    assert source is not None
    assert source.document_version == 2
    assert source.tags == ("guide",)
    assert await repository.count_index_chunks(tenant_id, document_id, 2) == 1
    page = await repository.list_index_chunks(tenant_id, document_id, 2, 0, 1)
    assert page[0].id == chunk_id
    assert await repository.get_index_source(uuid.uuid4(), document_id) is None

    candidate = IndexingJob(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        document_id=document_id,
        document_version=2,
        chunk_set_fingerprint=await repository.chunk_set_fingerprint(tenant_id, document_id, 2),
        collection_name="phoenix_test",
        embedding_fingerprint="b" * 64,
        model_name="test-model",
        model_version="test-version",
        total_vectors=1,
    )
    first = await repository.create_or_get_job(candidate)
    second = await repository.create_or_get_job(
        IndexingJob(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            document_id=document_id,
            document_version=2,
            chunk_set_fingerprint=first.chunk_set_fingerprint,
            collection_name="phoenix_test",
            embedding_fingerprint="b" * 64,
            model_name="test-model",
            model_version="test-version",
            total_vectors=1,
        )
    )
    assert first.id == second.id

    state = await repository.publish_version(
        DocumentIndexState(
            tenant_id=tenant_id,
            document_id=document_id,
            active_document_version=2,
            active_chunk_set_fingerprint=first.chunk_set_fingerprint,
            active_collection="phoenix_test",
            active_embedding_fingerprint="b" * 64,
        ),
        first,
    )
    assert state.active_document_version == 2
    assert await repository.active_versions(tenant_id) == {
        document_id: (2, first.chunk_set_fingerprint)
    }
    assert await repository.collection_is_active("phoenix_test")
    assert await repository.statistics(tenant_id) == {"indexed": 1}

    count = await seeded_session.scalar(select(IndexingJobModel.id).where(IndexingJobModel.id == first.id))
    assert count == first.id