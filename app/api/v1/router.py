"""Aggregates all v1 endpoint routers into a single APIRouter."""

from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, documents, health, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
