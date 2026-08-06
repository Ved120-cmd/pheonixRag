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
