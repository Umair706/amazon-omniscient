"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import ConnectionPool as RedisPool
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.router import router as api_router
from app.config import Settings

logger = structlog.stdlib.get_logger(__name__)


def _configure_logging(log_level: str) -> None:
    """Set up structlog with human-readable console output."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    import logging

    logging.basicConfig(format="%(message)s", level=getattr(logging, log_level.upper(), "INFO"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown resources."""
    settings = Settings()
    _configure_logging(settings.LOG_LEVEL)

    # ── Async SQLAlchemy engine + session factory ──────────────────────
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory
    logger.info("database_engine_created", url=settings.DATABASE_URL.split("@")[-1])

    # ── Redis connection pool ─────────────────────────────────────────
    redis_pool = RedisPool.from_url(settings.REDIS_URL, decode_responses=True)
    app.state.redis_pool = redis_pool
    logger.info("redis_pool_created", url=settings.REDIS_URL)

    yield

    # ── Shutdown ──────────────────────────────────────────────────────
    await Redis(connection_pool=redis_pool).aclose()
    await engine.dispose()
    logger.info("resources_cleaned_up")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="Omniscient",
        description="Amazon Product Research Engine",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── CORS (permissive for local development) ───────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Production middleware ──────────────────────────────────────
    from app.core.middleware import RequestLoggingMiddleware, GlobalExceptionMiddleware
    app.add_middleware(GlobalExceptionMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    # ── Routers ───────────────────────────────────────────────────────
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
