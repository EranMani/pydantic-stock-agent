"""Async SQLAlchemy engine, session factory, and FastAPI lifespan handler.

Three exports consumed by the rest of the application:

  engine               — the single AsyncEngine instance for this process
  async_session_factory — call to get an AsyncSession for a unit of work
  get_session          — FastAPI dependency: yields one AsyncSession per request
  lifespan             — passed to FastAPI(lifespan=lifespan); manages engine
                         startup and shutdown

Session contract:
  - expire_on_commit=False: attributes remain accessible after session.commit()
    without triggering a new DB round-trip. Required in async context — SQLAlchemy's
    default lazy-load on attribute access after commit would block the event loop.
  - Sessions are never created inside CRUD functions — always injected by the caller.
  - One session per HTTP request (managed by get_session dependency).
  - One session per Celery task (created manually via async_session_factory).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from stock_agent.config import settings
from stock_agent.db.models import Base

# ---------------------------------------------------------------------------
# Engine — created once per process, shared across all sessions.
# pool_pre_ping=True: test each connection before use; silently replaces
# stale connections dropped by Postgres or a network device after idle time.
# ---------------------------------------------------------------------------
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,        # persistent connections held open between requests
    max_overflow=10,    # extra connections allowed above pool_size under load
    pool_pre_ping=True, # validates connection health before handing it to a session
)

# ---------------------------------------------------------------------------
# Session factory — produces AsyncSession instances bound to the engine above.
# expire_on_commit=False: keep attribute values accessible after commit()
# without a lazy-load round-trip (which would block the async event loop).
# ---------------------------------------------------------------------------
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency — one session per HTTP request, closed after response.
# ---------------------------------------------------------------------------
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession for a single HTTP request.

    Usage in a route handler:
        async def my_route(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with async_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# FastAPI lifespan — engine startup and shutdown, wired to the app lifecycle.
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage async engine lifecycle for the FastAPI application.

    STARTUP:
      - In development (APP_ENV=development): auto-creates all tables via
        Base.metadata.create_all. Convenient for local dev without running
        Alembic manually. Never used in production — Alembic owns schema there.

    SHUTDOWN:
      - engine.dispose(): closes all pooled connections cleanly.
        Prevents connection leaks on server restart.
    """
    # STARTUP
    if settings.APP_ENV == "development":
        # Auto-create tables in dev — skipped in production (Alembic handles it)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    yield

    # SHUTDOWN
    await engine.dispose()
