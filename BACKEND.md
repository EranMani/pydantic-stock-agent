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
9. [Database Design Principles](#9-database-design-principles)
10. [Testing the Database Layer](#10-testing-the-database-layer)

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

---

### The Engine, Session Factory, and Lifespan (Step 40)

Three components in `db/session.py` that form the ground rules of all database connectivity.

---

#### The AsyncEngine

**One job: manage the connection pool.**

The engine doesn't run queries or know about ORM models. It owns a pool of TCP sockets to Postgres and hands them out when sessions need them.

```python
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,        # permanent connections, live for the server lifetime
    max_overflow=10,    # temporary connections created during traffic spikes
    pool_pre_ping=True, # health-check each connection before use
)
```

**Connection pool — the waiter analogy:**

| Setting | Meaning |
|---|---|
| `pool_size=5` | 5 permanent waiters, each with their own TCP socket to Postgres |
| `max_overflow=10` | Up to 10 temporary waiters hired during a rush, fired when done |
| Max concurrent connections | 5 + 10 = 15 |

**Permanent vs temporary connections:**
- **Permanent (pool_size)** — TCP socket opened lazily on first use, kept open for the server's lifetime. One handshake and authentication per waiter, done once.
- **Temporary (overflow)** — TCP socket opened when all permanents are busy, closed immediately after the request finishes. Not returned to the pool.

**`pool_pre_ping=True` — the shoulder tap:**
A connection in the pool can go stale while idle — Postgres kills it after a timeout, a firewall drops the TCP socket, Postgres restarts. The pool doesn't know. Without pre-ping, a stale connection gets handed to a request and fails. With pre-ping, a cheap `SELECT 1` fires before every handout. If it fails, the connection is discarded and a fresh one opened — the request never sees the failure. The pre-ping fires only when a connection is pulled from the pool, not while idle.

**When the engine is used directly (rare):**
```python
# dev startup — create tables
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)

# shutdown — close all sockets
await engine.dispose()

# Alembic — run migrations (bypasses session layer)
async with engine.begin() as conn:
    await conn.run_sync(do_run_migrations)
```

In normal application code, you never touch the engine. You work with sessions.

**Lazy vs eager connections:**
- **Production** — pool starts empty. First connection opens on the first user request. Server starts fast and tolerates brief DB unavailability during deploys.
- **Development** — lifespan runs `create_all` at startup, which opens the first connection immediately. Fails fast if `DATABASE_URL` is wrong or Postgres isn't running.

---

#### The Session Factory

**One job: dispense `AsyncSession` instances.**

```python
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

The session is your unit of work — one conversation with the database. It borrows a connection from the engine's pool, runs your queries, and returns the connection when done.

**`expire_on_commit=False` — required in async context:**

By default, SQLAlchemy expires all model attributes after `session.commit()`. The next attribute access triggers a lazy load — a new SQL query. In async context, that lazy load blocks the event loop and crashes:

```python
await session.commit()
print(record.ticker)  # default: triggers lazy load → blocks event loop → error
                       # expire_on_commit=False: reads from memory → safe
```

**Three ways sessions are used in this project:**

| Context | How |
|---|---|
| HTTP request | `Depends(get_session)` — FastAPI injects automatically |
| Celery task | `async with async_session_factory() as session:` — created manually |
| Dev startup | `engine.begin()` directly — DDL only, bypasses session |

---

#### `get_session` — the FastAPI Dependency

```python
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

`yield` is the key. It's not a traditional generator — it's a **dependency with cleanup**. FastAPI recognises the `yield` pattern and treats everything after it as teardown logic.

**The execution flow:**
```
FastAPI calls get_session()
→ session opens
→ yield session    ← pauses here, hands session to the route handler
→ route handler runs (session available throughout)
→ handler finishes (success or exception)
→ resumes after yield → async with closes session automatically
→ connection returned to pool
```

The session stays open for the **entire request lifetime** — not just until the last query. It closes only when the route handler finishes. Cleanup is guaranteed regardless of exceptions — no manual `session.close()` needed anywhere.

**Session lifetime = request lifetime.**

---

#### The Lifespan

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # STARTUP
    if settings.APP_ENV == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    # SHUTDOWN
    await engine.dispose()
```

Passed to `FastAPI(lifespan=lifespan)`. Runs startup before the server accepts any traffic, shutdown after the last request is handled.

**Why it exists:**

| Phase | What it does | Why |
|---|---|---|
| Startup (dev) | `create_all` — creates all tables | Tables must exist before requests arrive |
| Startup (prod) | Nothing | Alembic already ran before server started |
| Shutdown | `engine.dispose()` | Closes all TCP sockets cleanly; prevents connection leaks |

**The complete server lifecycle:**
```
Server starts
→ lifespan STARTUP: create tables (dev) or nothing (prod)
→ yield: server accepts requests
    → get_session opens/closes sessions per request
    → engine hands out/reclaims connections from pool
→ lifespan SHUTDOWN: engine.dispose() closes all sockets
Server exits
```

---

#### The Three-Layer Hierarchy

```
engine                     → owns TCP sockets to Postgres (pool)
  └── async_session_factory → dispenses sessions bound to the engine
        └── AsyncSession    → borrows one socket, runs queries, returns it
```

One engine per process. One factory per engine. Many sessions over time — one per request, one per Celery task, each short-lived and automatically cleaned up.

### The two ORM models (Step 39)

**`StockReportRecord`** → `stock_reports` table

Stores a completed analysis. Key decisions:
- `report_json: JSON` — full `StockReport` serialised; source of truth
- `fundamental_score / technical_score / weighted_score: Numeric(4, 1)` — **never `Float`**; `Numeric` stores exact decimals, `Float` introduces drift (7.1 → 7.09999...)
- `ticker`, `recommendation` denormalised alongside the JSON for fast queries without parsing
- `created_at: DateTime(timezone=True)` — always timezone-aware; `server_default=func.now()` set at the DB level

**`AnalysisJobRecord`** → `analysis_jobs` table

Tracks a Celery job lifecycle. Key decisions:
- `job_id: String(36)` — the stable UUID shared between this record and the Redis progress key (`job:{job_id}:progress`); has a `UNIQUE` constraint
- `status: String(20)` — values: `pending` → `running` → `complete` / `failed`
- `updated_at` — carries `onupdate=func.now()` so it auto-updates on every `session.commit()` that touches this row

### Why Numeric over Float for scores?

```python
# Float — imprecise, dangerous for financial data
score: float = 7.1
# stored in Postgres as 7.09999999999999964...

# Numeric(4, 1) — exact
score: Numeric = Decimal("7.1")
# stored in Postgres as exactly 7.1
```

`Numeric(4, 1)` means: 4 total digits, 1 after the decimal point. Accepts `1.0` through `10.0` with zero drift.

### File structure (Phase 8)

| File | Responsibility |
|---|---|
| `db/models.py` | ORM model definitions: `StockReportRecord`, `AnalysisJobRecord` ✅ Step 39 |
| `db/session.py` | Async engine, session factory, FastAPI `lifespan` hook ✅ Step 40 |
| `db/crud.py` | CRUD functions: `create_job()`, `update_job_status()`, `save_report()`, `get_report_by_ticker()`, `list_recent_jobs()` ✅ Step 42 |

---

## 4b. CRUD Layer — `db/crud.py` (Step 42)

The CRUD layer exists to give every database operation a single, testable home that is completely decoupled from the HTTP layer, the Celery worker, and the NiceGUI frontend. Route handlers and tasks call these functions without knowing anything about how data is stored — and the functions themselves never know who called them. This makes each layer independently testable and swappable. See QA.md Q38 for the full reasoning.

This is the **Facade pattern** (GoF): `crud.py` hides all SQLAlchemy complexity — `select()`, `session.add()`, `scalar_one_or_none()`, `db.refresh()` — behind a clean, intention-revealing interface. Callers see `create_job(db, ticker)`, not the machinery behind it.

Five async functions that cover the full job and report lifecycle. All accept an injected `AsyncSession` — sessions are never created inside CRUD functions. All queries use SQLAlchemy ORM exclusively — no raw SQL.

### The five functions

| Function | Returns | Purpose |
|---|---|---|
| `create_job(db, ticker)` | `AnalysisJobRecord` | Insert a new job row with status `"pending"`. Generates the stable `job_id` UUID used by both the DB record and the Redis progress key. |
| `update_job_status(db, job_id, status)` | `None` | Transition a job to `running`, `complete`, or `failed`. Silent no-op if the job doesn't exist. |
| `save_report(db, job_id, report)` | `StockReportRecord` | Persist a completed `StockReport`. Stores the full report as JSON and denormalises score columns for fast querying (see below). |
| `get_report_by_ticker(db, ticker)` | `StockReportRecord \| None` | Fetch the most recent report for a ticker, ordered by `created_at DESC`. Returns `None` if none exists. |
| `list_recent_jobs(db, limit=20)` | `list[AnalysisJobRecord]` | Return the N most recent job rows, newest first. Feeds the NiceGUI job history panel. |

### `db.refresh()` — why it is called after every commit

After `db.add()` + `await db.commit()`, PostgreSQL has the complete row including all server-generated values (`created_at`, `updated_at`). The in-memory Python object is still in the state it was constructed — timestamp fields are `None`. `await db.refresh(obj)` fires a `SELECT` on that specific row and overwrites the in-memory object with whatever PostgreSQL actually stored. After `refresh()`, the Python object is a true mirror of the DB row.

```python
db.add(job)              # Python object: job_id=✓, created_at=None
await db.commit()        # PostgreSQL row: job_id=✓, created_at=2026-03-24 11:32:00
await db.refresh(job)    # Python object: job_id=✓, created_at=2026-03-24 11:32:00 ✓
return job               # caller receives a fully populated object
```

Without `refresh()`, the caller would access `job.created_at` and get `None`. The session is configured with `expire_on_commit=False` (see Section 4), but that only prevents lazy-load crashes — it does not populate server-generated values. `refresh()` is still required for that.

### Denormalized score columns in `save_report`

`StockReportRecord` stores two representations of the report:

1. **`report_json`** — the full `StockReport` serialised via `model_dump(mode="json")`. Source of truth. Nothing is lost.
2. **`fundamental_score`, `technical_score`, `weighted_score`, `recommendation`** — typed columns copied from the report at insert time.

The dedicated columns exist so the API and UI can query, sort, and filter by score without deserialising the JSON blob on every row:

```sql
-- Fast — hits an indexed Numeric column
SELECT * FROM stock_reports WHERE weighted_score > 7.0 ORDER BY weighted_score DESC;

-- Slow alternative — requires JSON parsing per row
SELECT * FROM stock_reports WHERE report_json->>'weighted_score' > '7.0';
```

Scores are stored as `Decimal` via `Decimal(str(round(score, 1)))` to preserve `Numeric(4,1)` precision — float-to-Decimal conversion goes through `str()` to avoid IEEE 754 binary fraction drift.

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
| — | `Numeric(4, 1)` over `Float` for all score columns — prevents precision drift in Postgres | 39 |
| — | `job_id: String(36)` on `AnalysisJobRecord` is the stable Redis/DB shared identifier — never Celery's `task_id` | 39 |
| — | `expire_on_commit=False` on session factory — prevents lazy-load blocking the async event loop after `commit()` | 40 |
| — | `create_all` in dev mode only — production schema is always owned by Alembic, never by `metadata.create_all()` | 40 |

*More entries will be added as Phases 8–10 are built.*

---

## 9. Database Design Principles

Key concepts that guide every table and column decision in this project.

---

### When to create a separate table

Split into a separate table when an entity has:
- A **distinct lifecycle** — it is created and destroyed independently of other entities
- **Independent meaning** — it has value on its own, not just as a property of something else
- **Asymmetric existence** — one can exist without the other

Keep in the same table when fields are just **properties** of the same thing — they always appear together, always mean nothing in isolation.

**Example in this project:**
- `AnalysisJobRecord` and `StockReportRecord` → separate tables: a job can exist without a report; they have different lifecycles and different meaning
- `fundamental_score` and `technical_score` → same table (`stock_reports`): a score has no independent meaning — it's just a property of the report

---

### Command / Result separation (lightweight CQRS)

A pattern where the record of **what was requested** (command) is kept separate from the record of **what was produced** (result).

| Concept | Our implementation |
|---|---|
| Command | `AnalysisJobRecord` — "analyse this ticker was requested" |
| Result | `StockReportRecord` — "here is what the analysis produced" |

**The rule:** a result cannot exist without a command. A command can exist without a result.

This means:
- Every job request creates an `AnalysisJobRecord` immediately — always
- `StockReportRecord` is only created on successful completion — conditionally

**Why it matters:** on a server crash, you can query `AnalysisJobRecord` for all `pending` and `running` jobs and re-dispatch them. You always know what was asked for, regardless of whether it succeeded.

---

### `AnalysisJobRecord` as the ground pillar

The job record is created **first**, before anything else is dispatched:

```
1. FastAPI generates job_id (UUID)
2. INSERT AnalysisJobRecord  ← ground pillar
3. Celery task dispatched with job_id
4. job_id returned to UI for polling
```

Everything downstream — Celery, Redis, the UI polling loop — derives its identity from `job_id`. If the insert fails, nothing is dispatched. No orphaned jobs, no phantom Redis keys.

---

### `AnalysisJobRecord` as the operational dashboard

At any point the table answers operational questions:

| Query | Meaning |
|---|---|
| `status = 'pending'` | Enqueued, not yet picked up by a worker |
| `status = 'running'` | Worker is active — check Redis for live progress |
| `status = 'complete'` | `StockReportRecord` exists for this job |
| `status = 'failed'` | Pipeline error — no report produced |

After a crash: scan for `pending` / `running` rows and re-dispatch. The database is the recovery source — Redis is ephemeral and may not survive a restart.

---

## 10. Testing the Database Layer

---

### Why test ORM models at all?

A model definition is a contract — "this table exists, these columns exist, these constraints hold." The Python code compiling successfully does not prove the contract is true. It only proves the syntax is valid.

Tests are the proof that SQLAlchemy correctly translated your Python definitions into a real schema with the right shape, types, and behaviour. Without them, the only verification is "it looks right" — which is not acceptable for infrastructure that other systems depend on.

**The core rule:** if a failure would be silent at definition time but catastrophic at runtime, there must be a test for it.

---

### Two test tiers

**Tier 1 — SQLite in-memory (no infrastructure needed)**

Used for structural and round-trip tests. SQLite spins up in milliseconds inside the test process — no Docker, no running Postgres required.

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from stock_agent.db.models import Base

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)  # creates all tables in SQLite
```

Covers: table names, column presence, round-trip save/retrieve, type precision, constraints, `__repr__`.

**Tier 2 — Async Postgres (requires Docker Compose)**

Used for integration tests — real `AsyncSession`, real transactions, real CRUD functions. Added in Step 42 via `conftest.py` with an async test session fixture.

Covers: async CRUD functions, transaction rollback, concurrent access, real Postgres type behaviour.

---

### What to test for every ORM model

| What | Why |
|---|---|
| `__tablename__` value | A wrong table name means every query silently hits the wrong table |
| All column names present | Catches missing or renamed columns before they cause runtime errors |
| Round-trip save and retrieve | Proves the full persistence cycle works — not just that the class compiles |
| Numeric/Decimal precision | `Float` would silently store `6.299999...` instead of `6.3` — must be verified |
| NOT NULL constraints | Inserting without a required field should raise, not silently store NULL |
| UNIQUE constraints | A duplicate insert must raise `IntegrityError` — proves the DB enforces it |
| `__repr__` output | Debug output must include key identifiers — caught early, saves time later |

---

### How to run the tests

```bash
# Run only the database tests
uv run pytest tests/test_db.py -v

# Run only the worker tests
uv run pytest tests/test_worker.py -v

# Run both
uv run pytest tests/test_db.py tests/test_worker.py -v

# Run the full suite
uv run pytest
```

The `-v` flag prints each test name and its pass/fail status individually — essential when diagnosing a failure.

**Expected output for a clean run:**
```
tests/test_db.py::test_stock_report_record_table_name     PASSED
tests/test_db.py::test_analysis_job_record_table_name     PASSED
tests/test_db.py::test_stock_report_record_columns        PASSED
...
11 passed in 1.06s
```

---

### The test file location contract

| File | What it tests |
|---|---|
| `tests/test_db.py` | ORM models, session, CRUD — Rex owns this |
| `tests/test_worker.py` | Celery tasks, Redis publish — Rex owns this |
| `tests/conftest.py` | Shared fixtures (async session, mocked Redis) — added in Step 42 |

Rex never touches `tests/test_fundamental.py`, `tests/test_technical.py`, or `tests/test_ui.py` — those are Claude's and Aria's domains.
