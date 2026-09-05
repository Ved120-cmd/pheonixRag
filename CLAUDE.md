# Claude context for PhoenixRAG

This repository is a local PhoenixRAG application with FastAPI backend and a Next.js frontend.

## Key points

- Backend: `app/` contains FastAPI endpoints, auth, document ingestion, storage, and infrastructure adapters.
- Frontend: `my-app/` contains the Next.js client.
- Auth: JWT-based login and bearer token validation.
- Storage: Documents are stored in MinIO via S3-compatible `minio` client.
- Local runtime: `.env` points to localhost services (Postgres, Redis, Qdrant, MinIO).
- Known issue: `/health` times out even though individual services are reachable; `/docs` works.

## Local services

- Postgres: `localhost:5432`
- Redis: `localhost:6379`
- Qdrant: `localhost:6333`
- MinIO API: `localhost:9000`
- MinIO console: `localhost:9091`
- FastAPI: `localhost:8000`
- Next.js frontend: `localhost:3000`

## Helpful file locations

- `app/main.py`: application startup, CORS, middleware, router registration.
- `app/api/v1/router.py`: main API router, mounts `/api/v1` routes.
- `app/api/v1/endpoints/auth.py`: user auth routes: register, login, logout, refresh, forgot/reset password, verify email.
- `app/api/v1/endpoints/users.py`: current user routes: get/update `/me`, change password, delete account.
- `app/api/v1/endpoints/admin.py`: admin routes: list users, update user role/status.
- `app/api/v1/endpoints/documents.py`: upload/list/get/delete/restore documents.
- `app/api/v1/endpoints/health.py`: health check route.
- `app/application/services/document_service.py`: document storage and metadata registration.
- `app/infrastructure/storage/document_store.py`: MinIO put/get implementation.
- `app/infrastructure/storage/minio_client.py`: MinIO client configuration.
- `my-app/lib/documents.ts`: frontend document upload/list API.
- `.env`: local service hostnames and credentials.

## Notes

- MinIO appears reachable from the host and returns `403` on the base API port when unauthenticated.
- The repository currently has a temporary diagnostic script `health_diag.py` used for local checks.

## Recent updates (Phase 4 work)

- Added a document processing pipeline skeleton to support text extraction and structured results.
- New domain entity: `app/domain/entities/processing.py` (dataclass `ProcessingJob`).
- New SQLAlchemy model: `app/infrastructure/database/models/processing.py` (`processing_jobs` table).
- Mapper functions added to `app/infrastructure/database/mappers.py` to convert between `ProcessingModel` and `ProcessingJob`.
- Repository interface: `app/domain/repositories/processing_repository.py`.
- SQLAlchemy repository implementation: `app/infrastructure/database/repositories/processing_repository.py`.

Next steps planned:

- Implement parser strategy and initial parsers (`text`, `pdf`, `docx`, `markdown`).
- Add `ProcessingService` and Celery task to orchestrate parsing, retries, and persistence.
- Create API endpoints to enqueue processing jobs and fetch status/results/logs.
- Add unit and integration tests for parsers and the processing flow.

