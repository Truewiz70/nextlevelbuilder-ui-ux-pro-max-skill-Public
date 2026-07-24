"""Application factory.

Wires cross-cutting concerns (config, logging, error handlers, CORS) and
mounts module routers. Modules register here and nowhere else — no module
imports another module's internals.
"""

from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.db import check_database
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging, get_logger
from app.modules.conversation.providers import get_embedding_provider, get_llm_provider

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    app.state.redis = aioredis.from_url(settings.redis_url)
    # Provider clients are constructed once and reused — not per-request.
    # Tests override these on app.state after TestClient startup (fakes must
    # replace the real providers post-lifespan, or this assignment wins).
    app.state.llm_provider = get_llm_provider(settings)
    app.state.embedding_provider = get_embedding_provider(settings)
    logger.info("startup", env=settings.app_env)
    yield
    await app.state.redis.aclose()
    logger.info("shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_output=settings.app_env != "development")

    app = FastAPI(
        title="AI Receptionist API",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        """Liveness: the process is up."""
        return {"status": "ok", "version": app.version}

    @app.get("/readyz", tags=["health"])
    async def readyz() -> dict[str, str]:
        """Readiness: dependencies are reachable."""
        await check_database()
        await app.state.redis.ping()
        return {"status": "ready", "database": "ok", "redis": "ok"}

    # Module routers mount here as they land:
    from app.modules.telephony.routes import router as telephony_router

    app.include_router(telephony_router, prefix="/webhooks/voice", tags=["webhooks"])
    # Phase 4+: tenants, knowledge, calls, analytics API routers.

    return app


app = create_app()
