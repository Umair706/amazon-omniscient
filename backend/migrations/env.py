"""Alembic async-aware environment configuration.

Reads the database URL from ``app.config.Settings`` and uses an async
engine (asyncpg) so that migrations work against the same connection
pool the application uses at runtime.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import Settings

# Import Base *and* every model so that Base.metadata is fully populated
# before Alembic introspects it.
from app.models import Base  # noqa: F401 – side-effect import
from app.models import (  # noqa: F401 – side-effect imports
    BSRHistory,
    Competitor,
    FinancialProjection,
    LandedCostCalculation,
    Niche,
    NicheKeyword,
    PPCKeyword,
    PriceHistory,
    Product,
    Recommendation,
    Review,
    ReviewPainPoint,
    Supplier,
    UserSettings,
)

# ── Alembic Config object ──────────────────────────────────────────
config = context.config

# Interpret the config file for Python logging if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData target for autogenerate support
target_metadata = Base.metadata

# ── Inject the real DATABASE_URL from app settings ──────────────────
settings = Settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


# ── Offline mode (generates SQL script without a live DB) ───────────
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well.  By skipping the Engine
    creation we don't even need a DBAPI to be available.

    Calls to ``context.execute()`` here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online (async) mode ─────────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    """Execute migrations inside the provided synchronous connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations within its connection."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (async)."""
    asyncio.run(run_async_migrations())


# ── Entrypoint ──────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
