from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from eyes.server.api.dependencies import Database
from eyes.server.api.middleware import RequestBoundary, validation_details
from eyes.server.api.routes import router
from eyes.server.config import Settings
from eyes.server.domain import DomainError
from eyes.server.evidence.service import LocalArtifactStore
from eyes.server.storage.database import database

INITIAL_REVISION = "0001_control_plane"


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    engine, sessions = database(settings)
    provider = TracerProvider(resource=Resource.create({"service.name": "eyes-api"}))
    if settings.trace_console_export:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    tracer = provider.get_tracer("eyes.server")

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.dispose()
        provider.shutdown()

    app = FastAPI(title="Eyes Control API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.sessions = sessions
    app.state.artifacts = LocalArtifactStore(settings.artifact_root)
    app.add_middleware(RequestBoundary, settings=settings, tracer=tracer)
    app.include_router(router)

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
        return JSONResponse(
            status_code=exc.status,
            headers=headers,
            content={
                "schema_version": "1.0",
                "error": {"code": exc.code, "message": exc.message, "details": exc.details},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse(
            status_code=422,
            content={
                "schema_version": "1.0",
                "error": {
                    "code": "invalid_request",
                    "message": "request failed contract validation",
                    "details": validation_details(exc.errors()),
                },
            },
        )

    @app.exception_handler(IntegrityError)
    async def conflict(request, exc):
        return JSONResponse(
            status_code=409,
            content={
                "schema_version": "1.0",
                "error": {
                    "code": "integrity_conflict",
                    "message": "record conflicts with a persisted constraint",
                },
            },
        )

    @app.get("/health/live", tags=["health"])
    def live():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    def ready(session: Database):
        try:
            revision = session.scalar(text("SELECT version_num FROM alembic_version"))
        except SQLAlchemyError as exc:
            raise DomainError(
                503, "migration_required", "database is unavailable or not migrated"
            ) from exc
        if revision != INITIAL_REVISION:
            raise DomainError(503, "migration_required", "database revision does not match service")
        return {"status": "ready", "database_revision": revision}

    return app
