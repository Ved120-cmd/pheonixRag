# Phase 5 Chunking Engine

Phase 5 converts Phase 4 structured extraction results into reproducible document chunks. It does not implement embeddings, vector storage, retrieval, RAG, agents, or self-healing.

## Strategies

The strategy registry in `app/application/chunking/strategies.py` supports:

- `fixed`
- `recursive`
- `sliding_window`
- `semantic`
- `parent_child`

Strategies operate on `StructuredDocument` and `DocumentBlock` domain objects. They do not access FastAPI, SQLAlchemy, MinIO, or Celery.

## Local setup

```powershell
docker compose up -d postgres redis qdrant minio
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

For worker execution in a second terminal:

```powershell
celery -A app.application.tasks.chunk_document worker --loglevel=INFO --pool=solo
```

## API

All routes require a bearer token and verify document ownership:

```text
POST /api/v1/documents/{document_id}/chunking
POST /api/v1/documents/{document_id}/chunking/rechunk
PUT  /api/v1/documents/{document_id}/chunking/configuration
GET  /api/v1/documents/{document_id}/chunking/status
GET  /api/v1/documents/{document_id}/chunks
GET  /api/v1/documents/{document_id}/chunks/statistics
```

The request body contains `strategy`, `chunk_size`, `overlap`, `minimum_chunk_size`, `maximum_chunk_size`, `similarity_threshold`, `parent_size`, and `child_size`.

## Persistence

- `chunking_runs` stores status, attempts, warnings, statistics, and the exact configuration.
- `document_chunks` stores text, counts, page and section metadata, strategy, configuration, hashes, version, and parent references.
- Re-chunking marks old chunks inactive before inserting the new active version.
- Repeating the same completed configuration is idempotent unless `rechunk` or configuration update is used.

## Validation

The validator rejects empty and duplicate content, and records warnings for small/large chunks, broken text, excessive overlap, and missing metadata. Statistics include chunk count, character totals, average/minimum/maximum lengths, and token totals.

The token count is intentionally deterministic whitespace tokenization at this stage. A future tokenizer can be introduced behind the same chunk domain contract without changing persistence or API boundaries.
