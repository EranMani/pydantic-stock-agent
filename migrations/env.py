"""Alembic migration environment.

Reads DATABASE_URL from stock_agent.config.settings — never from alembic.ini.
Uses asyncpg (async driver) for online migrations via asyncio.run() bridge.
target_metadata will be set to Base.metadata in Step 39 when ORM models are defined.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import pool

from alembic import context

# Alembic Config object — access to .ini file values
config = context.config

# Set up loggers from the ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import settings to get DATABASE_URL at runtime — keeps secrets out of alembic.ini
from stock_agent.config import settings  # noqa: E402

# Import Base so Alembic can diff ORM models against the live schema (autogenerate).
# This import also registers StockReportRecord and AnalysisJobRecord with Base.metadata.
from stock_agent.db.models import Base  # noqa: E402

# Inject the URL programmatically so Alembic uses settings, not alembic.ini
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# target_metadata points at our ORM model registry — enables alembic revision --autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emits SQL without a live connection.

    Useful for generating migration SQL to review or run manually.
    Uses DATABASE_URL from settings (injected above).
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


def do_run_migrations(connection) -> None:
    """Execute pending migrations against the provided synchronous connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online_async() -> None:
    """Create an async engine and run migrations inside an async context.

    asyncpg is an async-only driver — we cannot use the synchronous
    engine_from_config path. We bridge back to sync via conn.run_sync().
    """
    engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,  # NullPool: no persistent connections during migrations
    )

    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)

    await engine.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to the live database."""
    asyncio.run(run_migrations_online_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
