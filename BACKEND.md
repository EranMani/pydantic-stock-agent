# Backend Infrastructure Reference

A living reference for the backend infrastructure layer of the Autonomous PydanticAI Stock Analyst Agent.
Covers PostgreSQL, SQLAlchemy ORM, Alembic, Celery, and Redis — updated as each phase is built.

Owner: **Rex** (senior backend engineer sub-agent)
Scope: `src/stock_agent/db/`, `src/stock_agent/worker/`, `migrations/`, `config.py` (backend fields)

---

## Table of Contents
1. [Technology Stack Overview](#1-technology-stack-overview)
2. [Configuration — Environment Variables](#2-configuration--environment-variables)
3. [PostgreSQL + asyncpg](#3-postgresql--asyncpg)
4. [SQLAlchemy ORM](#4-sqlalchemy-orm)
5. [Alembic — Database Migrations](#5-alembic--database-migrations)
6. [Celery — Background Workers](#6-celery--background-workers) *(Step 44+)*
7. [Redis — Broker & State Whiteboard](#7-redis--broker--state-whiteboard) *(Step 44+)*
8. [Design Decisions Index](#8-design-decisions-index)

---

## 1. Technology Stack Overview

```
FastAPI / NiceGUI app
        │
        │  async ORM operations (await session.execute(...))
        ▼
SQLAlchemy async engine  ←  AsyncSession
        │
        │  postgresql+asyncpg://  (URL scheme)
        ▼
    asyncpg driver         ←  async-only PostgreSQL driver
        │
        ▼
    PostgreSQL             ←  the actual database process
        │
        │  schema managed by
        ▼
    Alembic migrations     ←  versioned schema change history
```

**Why each layer exists:**
- **SQLAlchemy** — ORM: write Python classes, never raw SQL strings
- **asyncpg** — the only fully async PostgreSQL driver; required by SQLAlchemy's async engine
- **Alembic** — version-controls every schema change; lets us upgrade and rollback safely

---

## 2. Configuration — Environment Variables

All database connection parameters live in `config.py` as `Settings` fields. Nothing is hardcoded in logic files.

```python
# config.py (simplified)
class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/stockagent"
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"
```

### Understanding the DATABASE_URL

```
postgresql+asyncpg://  user  :  pass  @  localhost  :  5432  /  stockagent
                       ^^^^     ^^^^     ^^^^^^^^^    ^^^^    ^^^^^^^^^^
                       (1)      (2)        (3)         (4)       (5)
```

| Part | Meaning | Notes |
|---|---|---|
| `postgresql+asyncpg://` | Driver prefix | Tells SQLAlchemy to use asyncpg. Required for async engine. |
| `user` | Postgres role name | Created once via `CREATE USER` or docker-compose env |
| `pass` | Role password | Never hardcoded — always injected via environment variable |
| `localhost` | Host | `localhost` for local dev; `postgres` inside Docker Compose (service name) |
| `5432` | Port | Postgres default, almost never changed |
| `stockagent` | Database name | Created once via `CREATE DATABASE` or docker-compose env |

### Where to set these values

| Environment | Where to configure |
|---|---|
| Local development | `.env` file (read by `pydantic-settings` at startup) |
| Docker Compose | `environment:` block in `docker-compose.yml` |
| Production | Injected as runtime environment variables (never in Dockerfile) |

**.env** is for the **application** — it tells the app how to connect.
**docker-compose.yml** is for the **database container** — it tells Postgres what user and database to create on first boot.

The credentials must match across both. Example:

```yaml
# docker-compose.yml — creates the Postgres user and database
postgres:
  image: postgres:16
  environment:
    POSTGRES_USER: stockuser
    POSTGRES_PASSWORD: stockpass
    POSTGRES_DB: stockagent
```

```env
# .env — tells the app where to connect
DATABASE_URL=postgresql+asyncpg://stockuser:stockpass@postgres:5432/stockagent
```

Note: inside Docker Compose the host is the **service name** (`postgres`), not `localhost`.

---

## 3. PostgreSQL + asyncpg

### What is asyncpg?

`asyncpg` is a PostgreSQL **driver** — the library that speaks the network protocol to the actual Postgres process. It is the transport layer between Python and the database.

It is **async-only** by design. It does not support synchronous use — there is no blocking fallback. This is intentional: asyncpg was built from scratch on `asyncio` for maximum throughput and is the fastest Python PostgreSQL driver by benchmarks (it speaks the Postgres binary wire protocol directly, bypassing libpq).

### Why asyncpg specifically?

SQLAlchemy's async engine (`create_async_engine`) requires a driver that natively supports `asyncio`. asyncpg is the standard choice for the `postgresql+asyncpg://` URL scheme.

Without asyncpg, every database call would block the event loop — freezing the FastAPI server for all other requests while waiting for Postgres.

### The asyncpg constraint in Alembic

Alembic was designed for synchronous use. Its default migration runner calls `engine_from_config` (synchronous). asyncpg refuses to participate in synchronous calls.

The workaround in `migrations/env.py`:

```python
def run_migrations_online() -> None:
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)

    async def do_async_migrations() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(do_run_migrations)  # bridge: sync Alembic inside async context

    asyncio.run(do_async_migrations())  # bridge: async context from sync Alembic entry point
```

Two bridges stacked:
1. `conn.run_sync()` — lets Alembic's sync migration logic run inside an async connection
2. `asyncio.run()` — creates an event loop from Alembic's sync entry point

`NullPool` is used — migrations don't need a persistent connection pool; creating and immediately closing is correct here.

---

## 4. SQLAlchemy ORM

### What is an ORM?

ORM = **Object-Relational Mapper**. A layer that maps Python classes to database tables, so you interact with the database using Python objects rather than SQL strings.

```
Python class              Database table
─────────────             ──────────────
StockReportRecord    →    stock_reports
  ticker: str        →      ticker  VARCHAR
  score: float       →      score   FLOAT
  created_at         →      created_at TIMESTAMP
```

You define the class once in `models.py`. SQLAlchemy translates your Python operations into the correct SQL at runtime.

### Why ORM over raw SQL?

- **Type safety** — your IDE and Pydantic know the shape of your data
- **No SQL strings in logic files** — no risk of SQL injection, no scattered query strings
- **Database-agnostic** — swap Postgres for SQLite in tests without changing business logic
- **Consistent async pattern** — all `await session.execute(...)` calls integrate naturally into the async codebase

This is enforced as a non-negotiable rule: `ALWAYS use SQLAlchemy ORM for ALL database interactions — NEVER write raw SQL strings.`

### AsyncSession

`AsyncSession` is SQLAlchemy's async session class. Every ORM operation must be `await`ed:

```python
# Query example (Step 41+)
result = await session.execute(
    select(StockReportRecord).where(StockReportRecord.ticker == ticker)
)
record = result.scalar_one_or_none()
```

The `AsyncSession` is created by the session factory in `db/session.py` and injected into FastAPI route handlers via dependency injection. It lives for the lifetime of one HTTP request.

### File structure (Phase 8)

| File | Responsibility |
|---|---|
| `db/models.py` | ORM model definitions: `StockReportRecord`, `AnalysisJobRecord` |
| `db/session.py` | Async engine, session factory, FastAPI `lifespan` hook |
| `db/crud.py` | CRUD functions: `save_report()`, `get_report_by_ticker()`, `list_jobs()` |

---

## 5. Alembic — Database Migrations

### What is Alembic?

Alembic is **version control for your database schema**. Every time you change an ORM model (add a column, rename a field, add a table), you create a migration file. Alembic tracks which migrations have been applied and applies or rolls back changes safely.

Without Alembic: changing a model in Python silently falls out of sync with the actual Postgres schema → runtime crashes on missing columns.
With Alembic: every schema change is explicit, versioned, and reversible.

### File structure

```
alembic.ini              ← Alembic config (URL is NOT here — see DEC-020)
migrations/
├── env.py               ← wiring: connects Alembic to SQLAlchemy models + DB URL
├── script.py.mako       ← template for auto-generating migration files
└── versions/            ← one .py file per schema change (empty until Step 39)
    ├── 0001_create_stock_report_table.py
    └── 0002_add_index_on_ticker.py
```

### The workflow

```bash
# 1. After changing a model in db/models.py — generate a migration
uv run alembic revision --autogenerate -m "add score column to stock_reports"

# 2. Review the generated file in migrations/versions/ — always check before applying

# 3. Apply to the database
uv run alembic upgrade head

# 4. Roll back the last migration if needed
uv run alembic downgrade -1

# 5. Check current state
uv run alembic current
```

### How autogenerate works

Alembic diffs your ORM models (via `target_metadata = Base.metadata` in `env.py`) against the actual live database schema and writes the SQL `upgrade()` and `downgrade()` functions for you.

`target_metadata = None` until Step 39 — autogenerate is intentionally disabled until ORM models exist.

### DEC-020 — No credentials in alembic.ini

The default `alembic init` puts the database URL in `alembic.ini` — a plaintext committed file. This project injects the URL at runtime instead:

```python
# migrations/env.py
from stock_agent.config import settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
```

`alembic.ini` has no URL — the `sqlalchemy.url` line is replaced with a comment.
Single source of truth: `DATABASE_URL` always comes from `config.py` → environment variable.

See: **DEC-020** in `DECISIONS.md`.

---

## 6. Celery — Background Workers

*(This section will be filled in during Steps 44–47)*

**What it covers:**
- Why background workers exist (never block the FastAPI/NiceGUI event loop)
- Celery task definition pattern (`def`, not `async def`, with `asyncio.run()` bridge)
- Task anatomy: `run_fundamental_task`, `run_technical_task`, `run_scoring_task`
- Chord pattern for parallel + join execution
- Progress reporting to Redis under `job:{job_id}:progress`
- `CELERY_TASK_ALWAYS_EAGER` in tests

---

## 7. Redis — Broker & State Whiteboard

*(This section will be filled in during Steps 44–47)*

**What it covers:**
- Redis as Celery broker vs. result backend vs. progress state whiteboard
- The two Redis databases: `redis:6379/0` (broker) and `redis:6379/1` (results)
- Progress key contract: `job:{job_id}:progress` → `{"stage": str, "pct_complete": int, "message": str}`
- Why `job_id` (stable DB identifier) not `task_id` (changes per chord sub-task)
- NiceGUI polling pattern: `GET /jobs/{job_id}/status` → Redis read

---

## 8. Design Decisions Index

Backend-relevant entries in `DECISIONS.md`:

| ID | Decision | Step |
|---|---|---|
| DEC-020 | Alembic reads `DATABASE_URL` from `Settings` at runtime, not from `alembic.ini` | 38 |

*More entries will be added as Phases 8–10 are built.*
