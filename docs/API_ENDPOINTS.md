# API Endpoints and Progress

This document lists the current API endpoints in the PhoenixRAG backend and a short summary of what we've implemented so far.

## Base
- GET /docs - FastAPI Swagger UI
- GET /openapi.json - OpenAPI spec

## Auth (app/api/v1/endpoints/auth.py)
- POST /api/v1/auth/register - Register new user
- POST /api/v1/auth/login - Obtain JWT
- POST /api/v1/auth/logout - Revoke token
- POST /api/v1/auth/refresh - Refresh access token
- POST /api/v1/auth/forgot-password - Start reset flow
- POST /api/v1/auth/reset-password - Complete reset
- GET /api/v1/auth/verify-email - Email verification link

## Users (app/api/v1/endpoints/users.py)
- GET /api/v1/users/me - Get current user
- PATCH /api/v1/users/me - Update profile
- POST /api/v1/users/me/change-password - Change password
- DELETE /api/v1/users/me - Delete account

## Admin (app/api/v1/endpoints/admin.py)
- GET /api/v1/admin/users - List users
- PATCH /api/v1/admin/users/{user_id} - Update role/status

## Documents (app/api/v1/endpoints/documents.py)
- POST /api/v1/documents - Upload document (multipart/form-data `file`)
- GET /api/v1/documents - List documents (pagination)
- GET /api/v1/documents/{id} - Get document metadata
- GET /api/v1/documents/{id}/download - (frontend currently not wired) Download object from storage
- DELETE /api/v1/documents/{id} - Soft-delete
- POST /api/v1/documents/{id}/restore - Restore soft-deleted document

## Health (app/api/v1/endpoints/health.py)
- GET /api/v1/health - Aggregated health check (DB, Redis, MinIO, Qdrant)

## Processing (planned)
- POST /api/v1/processing - Enqueue processing for a document (not yet implemented)
- GET /api/v1/processing/{job_id} - Get processing job status/result (not yet implemented)
- GET /api/v1/processing/document/{document_id} - List processing jobs for a document (not yet implemented)
- POST /api/v1/processing/{job_id}/retry - Retry a failed job (not yet implemented)

## Chunking (Phase 5)
- POST /api/v1/documents/{document_id}/chunking - Start chunking with a configuration
- POST /api/v1/documents/{document_id}/chunking/rechunk - Force re-chunking
- PUT /api/v1/documents/{document_id}/chunking/configuration - Change configuration and re-chunk
- GET /api/v1/documents/{document_id}/chunking/status - Get latest run status and statistics
- GET /api/v1/documents/{document_id}/chunks - List active chunks
- GET /api/v1/documents/{document_id}/chunks/statistics - Get chunking statistics

## What we've implemented so far
- Core auth, users, admin, documents endpoints are implemented and in use.
- Document storage uses MinIO via `app/infrastructure/storage/document_store.py`.
- Document metadata persists in the DB via `DocumentModel` and repository patterns.
- Phase 4 groundwork added: `ProcessingJob` entity, `ProcessingModel`, mappers, and repository implementation.

## Next actions to finish processing flow
1. Implement parsers (text/pdf/docx/markdown) under `app/application/parsers/`.
2. Implement `ProcessingService` and Celery task to run parsing and persist results.
3. Implement API endpoints under `app/api/v1/endpoints/processing.py`.
4. Add tests and update docs.

