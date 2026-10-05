# PhoenixRAG

Self-Healing Multi-Agent RAG Platform — **Phase 2: Identity & Access Management**.

Phase 1 delivered production infrastructure (FastAPI, Postgres, Redis, Qdrant, MinIO).
Phase 2 adds authentication, authorization (RBAC), and user management.

## Quickstart

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.seed_iam
curl http://localhost:8000/health
```

Default bootstrap admin (change in production via `.env`):

| Field | Default |
|-------|---------|
| Email | `admin@phoenixrag.local` |
| Username | `admin` |
| Password | `ChangeMe!Admin1` |

Interactive API docs: http://localhost:8000/docs

## IAM API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login (returns JWT tokens) |
| POST | `/api/v1/auth/logout` | Revoke refresh token |
| POST | `/api/v1/auth/refresh` | Rotate refresh token |
| POST | `/api/v1/auth/forgot-password` | Request password reset |
| POST | `/api/v1/auth/reset-password` | Reset password with token |
| POST | `/api/v1/auth/verify-email` | Verify email with token |
| GET | `/api/v1/users/me` | Get current user |
| PATCH | `/api/v1/users/me` | Update profile |
| PATCH | `/api/v1/users/me/password` | Change password |
| DELETE | `/api/v1/users/me` | Delete account |
| GET | `/api/v1/admin/users` | List users (admin) |
| PATCH | `/api/v1/admin/users/{id}/role` | Change user role |
| PATCH | `/api/v1/admin/users/{id}/status` | Activate/deactivate user |

## Development

```bash
pip install -e ".[dev]"
pre-commit install
pytest -m unit
pytest -m integration
alembic upgrade head
python -m app.scripts.seed_iam
```

## Embedding Engine (Phase 6)

Phase 6 generates local embeddings for active, versioned document chunks using
Sentence Transformers and `BAAI/bge-small-en-v1.5` by default. PostgreSQL stores
job and embedding metadata only; vector storage and indexing are intentionally
reserved for Phase 7.

Embedding workers use Celery and Redis. Install dependencies, apply migrations,
and run a worker with:

```bash
pip install -e ".[dev]"
alembic upgrade head
celery -A app.infrastructure.tasks.celery_app.celery_app worker --loglevel=INFO
```

The benchmark harness compares batch sizes without changing application code:

```bash
python scripts/benchmark_embeddings.py --batch-size 32 --chunks 128
```

## Vector Indexing (Phase 7)

Apply the Phase 7 PostgreSQL migration and run a Celery worker to index the
current version's completed embeddings into Qdrant:

```bash
alembic upgrade head
celery -A app.infrastructure.tasks.celery_app.celery_app worker --loglevel=INFO
```

Set `QDRANT_URL`, optionally `QDRANT_API_KEY`, and configure
`QDRANT_COLLECTION_PREFIX`, `QDRANT_DISTANCE`, `QDRANT_INDEXING_BATCH_SIZE`,
and `QDRANT_TENANT_SHARDING` in the environment. Use Qdrant Server for tenant
shards and payload indexes; the in-memory client used by tests does not implement
sharding. Collection dimensions and embedding identity are verified before
upsert. Document versions are published through PostgreSQL only after all
current-version batches are acknowledged.

Synthetic Qdrant throughput, latency, batch-size, concurrent-job, and traced
memory measurements can be run with:

```bash
python scripts/benchmark_vector_indexing.py --batch-sizes 32 64 128 256 --vectors-per-job 1000 --concurrent-jobs 2
```
