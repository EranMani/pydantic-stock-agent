# Autonomous PydanticAI Stock Analyst Agent
**Architect:** Eran | **Mission:** Deterministic data pipelines → PydanticAI structured output
This project is built by following a strict **62-step Atomic Commit Protocol** (see Section 6).

---

## Section 2 — Development Commands

```bash
uv sync                                                                  # install all dependencies
uv run python -m stock_agent.main                                        # run CLI
uv run python -m stock_agent.ui.app                                      # run NiceGUI web server
uv run celery -A stock_agent.worker.celery_app worker --loglevel=info    # start Celery worker
uv run alembic upgrade head                                              # apply database migrations
uv run pytest                                                            # run full test suite
uv add <package>                                                         # add a dependency
docker build -t stock-agent .                                            # build production image
docker-compose up --build                                                # app + worker + redis + postgres + ollama
```

---

## Section 3 — Non-Negotiable Rules

- `ALWAYS minimize LLM usage` — ALL numerical calculations MUST be completed by the deterministic pandas-ta pipeline BEFORE any LLM is invoked; the LLM reasons over pre-computed data only, it NEVER computes data itself
- `ALWAYS use the local Ollama model (llama3.2 via PydanticAI OllamaModel)` for high-volume NLP tasks (news summarization, risk flag extraction); `ALWAYS use the cloud model (OpenAI/Gemini)` exclusively for final structured reasoning and StockReport generation
- `NEVER hardcode ticker symbols, API keys, or financial thresholds` in logic files — ALL constants live in `config.py`
- `NEVER allow the AI agent to compute or estimate any numerical indicator` — ALL technical calculations MUST go through the deterministic pandas-ta indicator modules
- `NEVER add a new indicator directly to core_data.py` — ALL indicators belong in `pipelines/technical/indicators/` as their own module
- `ALWAYS use type hints on every function signature` — no bare dicts or `Any` types in production modules
- `ALWAYS use async/await for all I/O operations` (yfinance, web search, tvDatafeed)
- `NEVER skip the NaN validation step (core_data.py)` before passing a DataFrame to any indicator module
- `ALWAYS respect ScoringStrategy when computing scores` — scorers must dynamically route based on the strategy config, not hardcode which metrics to include
- `NEVER fetch more than the yfinance industry peers list` for similar-stock analysis — do NOT attempt full-market screening
- `ALWAYS use SQLAlchemy ORM for ALL database interactions` — NEVER write raw SQL strings
- `ALWAYS offload all data fetching and agent scoring to Celery background workers` — NEVER call pipeline functions directly from the FastAPI or NiceGUI layer
- `NEVER block the NiceGUI event loop` — ALL long-running work dispatches a Celery task and returns immediately; progress is communicated exclusively via Redis
- `ALWAYS write Celery task progress updates to Redis under the key job:{job_id}:progress` as a JSON object with fields: `stage`, `pct_complete`, `message` — use `job_id` (the stable DB identifier) NOT the Celery `task_id` (which changes per sub-task in a chord)
- `ALWAYS define Celery tasks as synchronous functions (def, not async def)` — NEVER use `await` inside a `@celery.task` body; instead, delegate to a private `async def _async_*()` function and call it via `asyncio.run(_async_*())`
- `ALWAYS follow the exact commit message from the protocol` before moving to the next step
- `NEVER write JavaScript, CSS, or HTML files` — ALL frontend code must be implemented using NiceGUI's Python API exclusively
- `NEVER store secrets in the Dockerfile or docker-compose.yml` — ALL sensitive values must be injected via environment variables at runtime
- `NEVER merge Phase N+1 work into a Phase N commit` — one logical unit per commit, exactly as defined in the protocol

---

## Section 4 — Architecture Blueprint

```
pydantic-stock-agent/
├── Dockerfile                         # Multi-stage production image
├── docker-compose.yml                 # Local dev: 5-service stack
├── .github/
│   └── workflows/
│       ├── ci.yml                     # Lint + test on every PR
│       └── cd.yml                     # Build + push to ECR on main merge
├── src/stock_agent/
│   ├── main.py                        # CLI entry point — argparse + async run()
│   ├── agent.py                       # PydanticAI Agent definition, tool registration
│   ├── config.py                      # Central config: API keys, thresholds, constants
│   ├── models/
│   │   ├── report.py                  # StockReport, FundamentalData, TechnicalData, PeerReport
│   │   └── context.py                 # AgentDependencies, ScoringStrategy (dynamic metric selection)
│   ├── pipelines/
│   │   ├── fundamental/
│   │   │   ├── yf_client.py           # yfinance: market cap, P/E, earnings, revenue, peers
│   │   │   └── web_search.py          # DuckDuckGo: news search, risk/lawsuit flag parsing
│   │   └── technical/
│   │       ├── core_data.py           # tvDatafeed OHLCV extraction + NaN validation
│   │       └── indicators/
│   │           ├── moving_averages.py # SMA 50/150/200, 52-week high/low
│   │           ├── macd.py            # MACD line, signal, histogram
│   │           └── trend_setups.py    # Minervini Trend Template checks, VCP detector
│   ├── tools/
│   │   ├── fundamental_tools.py       # @agent.tool: news search, risk flags, peer list
│   │   └── technical_tools.py         # @agent.tool: wrappers for dynamic indicator requests
│   ├── scoring/
│   │   ├── fundamental_scorer.py      # calculate_fundamental_score(data, strategy) -> float
│   │   └── technical_scorer.py        # calculate_technical_score(df, strategy) -> TechnicalData
│   ├── db/
│   │   ├── models.py                  # SQLAlchemy ORM models: StockReportRecord, AnalysisJobRecord
│   │   ├── session.py                 # Async engine, session factory, lifespan handler
│   │   └── crud.py                    # save_report(), get_report_by_ticker(), list_jobs()
│   ├── worker/
│   │   ├── celery_app.py              # Celery instance, broker/backend config from settings
│   │   ├── state.py                   # publish_progress() — writes job:{job_id}:progress to Redis
│   │   └── tasks.py                   # @celery.task: run_fundamental_task, run_technical_task, run_scoring_task
│   └── ui/
│       ├── app.py                     # NiceGUI app mounted on FastAPI, entry point
│       ├── components/
│       │   ├── report_card.py         # StockReport display: score gauges, recommendation badge
│       │   ├── peer_table.py          # PeerReport comparison table
│       │   ├── strategy_panel.py      # ScoringStrategy config: metric toggles, weight sliders
│       │   ├── progress_panel.py      # Real-time Redis progress bar and status feed
│       │   └── dev_tools.py           # Dev-only panel: stress test trigger + 10 concurrent progress bars
│       └── theme.py                   # Dark theme, color palette, shared style constants
├── migrations/                        # Alembic migrations directory (auto-generated)
├── scripts/                           # Dev/ops utilities — repo root, excluded from Docker image
│   └── stress_test.py                 # Dispatches 10 concurrent Celery jobs via asyncio.gather()
└── tests/
    ├── conftest.py                    # pytest fixtures with mocked yfinance/tvDatafeed/redis
    ├── test_fundamental.py
    ├── test_technical.py
    ├── test_db.py                     # SQLAlchemy CRUD unit tests with async test session
    ├── test_worker.py                 # Celery task tests with eager mode (CELERY_TASK_ALWAYS_EAGER)
    └── test_ui.py                     # NiceGUI component smoke tests
```

**Key architectural decisions:**
- `pipelines/fundamental/` and `pipelines/technical/` are packages — prevents monolithic growth
- `config.py` centralizes ALL constants — nothing hardcoded in logic files
- `models/context.py` holds `ScoringStrategy` — dynamic metric selection without scorer interface changes
- `tools/technical_tools.py` enables agentic indicator lookups — LLM can proactively request a specific indicator mid-analysis
- `models/report.py` includes `PeerReport` — uses yfinance industry peers (5-10 tickers), no full-market screener
- `ui/` is pure Python NiceGUI — no JS, CSS, or HTML files anywhere in the repo
- `worker/tasks.py` Celery tasks write JSON progress to `job:{job_id}:progress`; NiceGUI polls `GET /jobs/{job_id}/status`
- **Hybrid model routing:** local Ollama (`llama3.2`) for news NLP; cloud model for final `StockReport` generation
- `db/` is strictly ORM-only — SQLAlchemy async + Alembic; zero raw SQL
- `docker-compose.yml`: five services — `app`, `worker`, `redis`, `postgres`, `ollama`; worker reaches Ollama at `http://ollama:11434`
- `scripts/` at repo root — excluded from production image via `COPY src/ ./src/`

**GoF Design Patterns:**
- **Strategy** — `ScoringStrategy` dynamically routes calculations without changing the scorer interface
- **Facade** — `run_scoring_task` chord hides full pipeline complexity behind a single `.delay()` call
- **Chain of Responsibility** — `indicators/` pipeline: each module appends columns and passes the DataFrame forward

---

## Section 5 — Tech Stack

- **Agent core:** `pydantic-ai>=0.0.14`, `pydantic>=2.7`, `fastapi`, `httpx`, `logfire`
- **Models:** Cloud — OpenAI / Gemini (final reasoning) | Local — `ollama` running `llama3.2` (NLP via PydanticAI `OllamaModel`)
- **Data:** `yfinance>=0.2`, `tvdatafeed`, `pandas-ta`, `python-dotenv`
- **Search:** `duckduckgo-search`
- **Frontend:** `nicegui` (Python-only, mounts on FastAPI)
- **Workers:** `celery>=5`, `redis` (Celery broker + real-time state whiteboard)
- **Database:** `postgresql` + `sqlalchemy[asyncio]>=2`, `alembic`, `asyncpg`
- **Testing:** `pytest`, `pytest-asyncio`
- **DevOps:** Docker (multi-stage, 5-service compose), GitHub Actions (CI/CD → AWS ECR)

---

## Section 6 — Protocol Reference

```
@.claude/commit-protocol.md
```

This single line causes Claude Code to lazy-load the full 62-step roadmap when needed.

---

## Section 7 — Environment Variables

`.env` keys required:

- `LOGFIRE_TOKEN` — optional, for observability
- `TV_USERNAME`, `TV_PASSWORD` — optional TradingView credentials for tvDatafeed
- `APP_ENV` — `development` | `production`
- `PORT` — web server port (default `8080`)
- `DATABASE_URL` — `postgresql+asyncpg://user:pass@postgres:5432/stockagent`
- `REDIS_URL` — `redis://redis:6379/0` (broker and state whiteboard)
- `CELERY_BROKER_URL` — `redis://redis:6379/0`
- `CELERY_RESULT_BACKEND` — `redis://redis:6379/1`
- `OLLAMA_HOST` — `http://ollama:11434` (Docker) | `http://localhost:11434` (local dev)
- `AWS_REGION`, `ECR_REPOSITORY` — populated by CI/CD pipeline at deploy time
