"""PhoenixRAG FastAPI application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.api.dependencies.middleware import RequestLoggingMiddleware
from app.api.exception_handlers import register_exception_handlers
from app.api.v1.router import api_router
from app.config.settings import get_settings
from app.infrastructure.logging.logger import configure_logging, get_logger

settings = get_settings()
configure_logging()
logger = get_logger("phoenixrag.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    logger.info("application_startup", extra={"app_env": settings.app_env})
    yield
    logger.info("application_shutdown")


app = FastAPI(
    title=settings.app_name,
    description="Self-Healing Multi-Agent RAG Platform — Phase 2: Identity & Access Management",
    version="0.2.0",
    debug=settings.app_debug,
    lifespan=lifespan,
)

register_exception_handlers(app)
allowed_origins = list(
    dict.fromkeys(
        [
            *settings.cors_origins,
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ]
    )
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(api_router, prefix="/api/v1")

from app.api.v1.endpoints import admin, auth, users

app.include_router(auth.router, prefix="/auth", tags=["auth"], include_in_schema=False)
app.include_router(users.router, prefix="/users", tags=["users"], include_in_schema=False)
app.include_router(admin.router, prefix="/admin", tags=["admin"], include_in_schema=False)




def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]


@app.get("/health", tags=["health"], include_in_schema=False)
async def root_health_redirect():
    """Convenience alias so orchestrators (Docker/Compose HEALTHCHECK) can
    hit /health directly without the /api/v1 prefix.
    """
    from app.api.v1.endpoints.health import health_check

    return await health_check()
