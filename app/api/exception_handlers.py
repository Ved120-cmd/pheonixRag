from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    AccountLockedError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    InactiveAccountError,
    NotFoundError,
    RateLimitExceededError,
    ValidationError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValidationError)
    async def validation_error_handler(_request: Request, exc: ValidationError) -> JSONResponse:
        detail: dict[str, str | list[dict[str, str]]] = {"message": exc.message, "code": exc.code}
        if exc.field:
            detail["errors"] = [{"field": exc.field, "message": exc.message}]
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(ConflictError)
    async def conflict_error_handler(_request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(_request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(InactiveAccountError)
    async def inactive_error_handler(_request: Request, exc: InactiveAccountError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(AuthorizationError)
    async def authorization_error_handler(
        _request: Request, exc: AuthorizationError
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(AccountLockedError)
    async def locked_error_handler(_request: Request, exc: AccountLockedError) -> JSONResponse:
        return JSONResponse(status_code=423, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(RateLimitExceededError)
    async def rate_limit_error_handler(
        _request: Request, exc: RateLimitExceededError
    ) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(NotFoundError)
    async def not_found_error_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": exc.message, "code": exc.code})

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.message, "code": exc.code})
