# Atomic Commit Protocol — Autonomous PydanticAI Stock Analyst Agent

**62 atomic commits across 11 phases.**
Execute steps in order. Do not combine steps. Do not skip steps.
Each commit message is exact — copy it verbatim.

---

## Phase 1: Project Setup & Core Schemas (Steps 1–5)

### Step 1 — `chore: initialize python project structure and virtual environment`
**Target files:** `pyproject.toml`, `src/stock_agent/__init__.py`, `.gitignore`, `.python-version`
**Key signatures:**
- `pyproject.toml` — `[project]` name `stock-agent`, requires-python `>=3.12`, `[build-system]` uses `hatchling`
- `.python-version` — `3.12`
**Acceptance criteria:** `uv sync` completes with no errors; `uv run python --version` prints `3.12.x`.

---

### Step 2 — `chore: install core dependencies (pydantic-ai, httpx, logfire)`
**Target files:** `pyproject.toml`
**Key signatures:**
- `uv add "pydantic-ai>=0.0.14" "pydantic>=2.7" fastapi "httpx[asyncio]" logfire uvicorn python-dotenv`
**Acceptance criteria:** `uv run python -c "import pydantic_ai; import fastapi; import logfire"` exits with code 0.

---

### Step 3 — `feat: define StockReport and PeerReport pydantic models`
**Target files:** `src/stock_agent/models/report.py`
**Key signatures:**
- `class FundamentalData(BaseModel)` — fields: `pe_ratio: float | None`, `revenue_growth: float | None`, `market_cap: float | None`, `beta: float | None`, `score: float`
- `class TechnicalData(BaseModel)` — fields: `sma_50: float`, `sma_150: float`, `sma_200: float`, `high_52w: float`, `low_52w: float`, `trend_template_passed: bool`, `vcp_detected: bool`, `score: float`
- `class PeerReport(BaseModel)` — fields: `ticker: str`, `weighted_score: float`, `recommendation: Literal["BUY", "WATCH", "AVOID"]`
- `class StockReport(BaseModel)` — fields: `ticker: str`, `analysis_date: datetime`, `fundamental_score: float`, `technical_score: float`, `weighted_score: float`, `summary: str`, `recommendation: Literal["BUY", "WATCH", "AVOID"]`, `peers: list[PeerReport]`
**Acceptance criteria:** `python -c "from stock_agent.models.report import StockReport"` runs without errors.

---

### Step 4 — `feat: define FundamentalData and TechnicalData sub-models`
**Target files:** `src/stock_agent/models/report.py`
**Key signatures:**
- Both `FundamentalData` and `TechnicalData` gain `model_config = ConfigDict(frozen=True)` — immutable after creation
- All numeric fields include `Field(ge=0.0)` constraints where applicable
**Acceptance criteria:** Attempting to mutate a `FundamentalData` instance raises a `ValidationError`; all field constraints are enforced on instantiation.

---

### Step 5 — `feat: setup AgentDependencies and ScoringStrategy for dynamic config`
**Target files:** `src/stock_agent/models/context.py`
**Key signatures:**
- `class ScoringStrategy(BaseModel)` — fields: `fundamental_metrics: list[str] = ["pe_ratio", "revenue_growth"]`, `technical_indicators: list[str] = ["trend_template", "vcp"]`, `fundamental_weight: float = 0.50`, `technical_weight: float = 0.50`; `@model_validator(mode="after") def weights_sum_to_one(self)` — raises `ValueError` if `fundamental_weight + technical_weight != 1.0`
- `@dataclass class AgentDependencies` — field: `strategy: ScoringStrategy`
**Acceptance criteria:** `ScoringStrategy(fundamental_weight=0.6, technical_weight=0.3)` raises `ValueError`; valid weights instantiate cleanly.

---

## Phase 2: Fundamental Data Pipeline (Steps 6–12)

### Step 6 — `chore: install and configure yfinance and duckduckgo-search, establish Settings class with base app config`
**Target files:** `pyproject.toml`, `src/stock_agent/config.py`
**Key signatures:**
- `uv add "yfinance>=0.2" duckduckgo-search`
- `class Settings(BaseSettings)` — fields: `TV_USERNAME: str = ""`, `TV_PASSWORD: str = ""`, `LOGFIRE_TOKEN: str = ""`, `APP_ENV: str = "development"`, `PORT: int = 8080`; reads from `.env` via `model_config = SettingsConfigDict(env_file=".env")`
- `settings = Settings()` — module-level singleton
**Acceptance criteria:** `from stock_agent.config import settings` imports cleanly; `settings.APP_ENV` defaults to `"development"`.

---

### Step 7 — `feat: implement async fetching of market cap and basic valuation ratios`
**Target files:** `src/stock_agent/pipelines/fundamental/yf_client.py`
**Key signatures:**
- `async def fetch_valuation_metrics(ticker: str) -> dict[str, float | None]` — uses `asyncio.to_thread(yf.Ticker(ticker).info.get, ...)` to wrap yfinance's synchronous `.info` call; returns `pe_ratio`, `beta`, `market_cap`
**Acceptance criteria:** `asyncio.run(fetch_valuation_metrics("AAPL"))` returns a dict with the three keys; no blocking call on the event loop (confirmed by `asyncio.to_thread` usage in code review).

---

### Step 8 — `feat: extract recent earnings and revenue growth metrics via yfinance`
**Target files:** `src/stock_agent/pipelines/fundamental/yf_client.py`
**Key signatures:**
- `async def fetch_earnings_growth(ticker: str) -> dict[str, float | None]` — extracts `revenueGrowth`, `earningsGrowth` from `yf.Ticker(ticker).info` via `asyncio.to_thread`
- `async def fetch_industry_peers(ticker: str) -> list[str]` — returns `yf.Ticker(ticker).info.get("industry", "")` peers; falls back to empty list on error
**Acceptance criteria:** Both functions return typed dicts/lists; `fetch_industry_peers("AAPL")` returns at most 10 tickers.

---

### Step 9 — `chore: verify duckduckgo-search integration`
**Target files:** `src/stock_agent/pipelines/fundamental/web_search.py`
**Key signatures:**
- `async def search_company_news(ticker: str, company_name: str, max_results: int = 10) -> list[str]` — uses `asyncio.to_thread(DDGS().text, ...)` to wrap the synchronous DuckDuckGo call; returns list of article snippets
**Acceptance criteria:** `asyncio.run(search_company_news("AAPL", "Apple Inc"))` returns a non-empty list of strings with no import errors.

---

### Step 10 — `feat: implement web search tool for recent company catalysts and news`
**Target files:** `src/stock_agent/pipelines/fundamental/web_search.py`
**Key signatures:**
- `async def search_recent_catalysts(ticker: str, company_name: str) -> list[str]` — queries `"{ticker} {company_name} catalyst earnings news {current_year}"` via DuckDuckGo
- `async def search_risk_news(ticker: str, company_name: str) -> list[str]` — queries `"{ticker} lawsuit SEC investigation risk {current_year}"`
**Acceptance criteria:** Both queries return results; query strings include the current year (not hardcoded).

---

### Step 11 — `feat: build text-parsing logic to flag potential risks or lawsuits`
**Target files:** `src/stock_agent/pipelines/fundamental/web_search.py`
**Key signatures:**
- `RISK_KEYWORDS: list[str]` — module-level constant list: `["lawsuit", "SEC", "investigation", "fraud", "recall", "fine", "penalty", "bankruptcy"]`
- `def extract_risk_flags(articles: list[str]) -> list[str]` — returns snippets containing any `RISK_KEYWORDS` match (case-insensitive)
**Acceptance criteria:** `extract_risk_flags(["Apple faces SEC investigation over..."])` returns the matching snippet; an empty articles list returns `[]`.

---

### Step 12 — `feat: create fundamental scoring algorithm (1-10) based on earnings and catalysts`
**Target files:** `src/stock_agent/scoring/fundamental_scorer.py`
**Key signatures:**
- `def calculate_fundamental_score(data: FundamentalData, strategy: ScoringStrategy) -> float` — dynamically weights only the metrics listed in `strategy.fundamental_metrics`; clamps output to `[1.0, 10.0]`
- Metric weights defined as `METRIC_WEIGHTS: dict[str, float]` module-level constant in `config.py`
**Acceptance criteria:** Calling with a strategy that excludes `"pe_ratio"` produces the same result regardless of the `pe_ratio` field value; output is always in `[1.0, 10.0]`.

---

## Phase 3: Technical Data Ingestion (Steps 13–17)

### Step 13 — `chore: install tvdatafeed and pandas-ta`
**Target files:** `pyproject.toml`
**Key signatures:**
- `uv add tvdatafeed "pandas-ta>=0.3"`
**Acceptance criteria:** `uv run python -c "from tvDatafeed import TvDatafeed, Interval; import pandas_ta"` exits with code 0.

---

### Step 14 — `feat: implement OHLCV daily data extraction for the requested ticker`
**Target files:** `src/stock_agent/pipelines/technical/core_data.py`
**Key signatures:**
- `def get_tv_client() -> TvDatafeed` — returns a `TvDatafeed(settings.TV_USERNAME, settings.TV_PASSWORD)` instance (anonymous if credentials empty)
- `async def fetch_ohlcv(ticker: str, exchange: str = "NASDAQ", n_bars: int = 300) -> pd.DataFrame`
- `def validate_ohlcv(df: pd.DataFrame) -> pd.DataFrame` — fills NaN, raises `ValueError` if fewer than 200 rows remain after cleaning

**Critical implementation note:** `tvDatafeed.get_hist()` is a **synchronous, blocking** call. It MUST be wrapped with `asyncio.to_thread()` to avoid blocking the event loop inside the Celery `_async_*` coroutine:

```python
async def fetch_ohlcv(ticker: str, exchange: str = "NASDAQ", n_bars: int = 300) -> pd.DataFrame:
    tv = get_tv_client()
    df = await asyncio.to_thread(tv.get_hist, ticker, exchange, interval=Interval.in_daily, n_bars=n_bars)
    return validate_ohlcv(df)
```

**Acceptance criteria:** `fetch_ohlcv` is an `async def` containing no direct `tv.get_hist()` call outside of `asyncio.to_thread()`; confirmed via code review in the acceptance test.

---

### Step 15 — `feat: add data validation and NaN handling for missing trading sessions`
**Target files:** `src/stock_agent/pipelines/technical/core_data.py`
**Key signatures:**
- `validate_ohlcv(df)` fills forward/backward NaN with `df.ffill().bfill()`; asserts required columns `["open", "high", "low", "close", "volume"]` exist; raises `ValueError("Insufficient data")` if `len(df) < 200`
**Acceptance criteria:** A DataFrame with 5 NaN rows in the middle passes validation after fill; a DataFrame with 150 rows raises `ValueError`.

---

### Step 16 — `feat: authenticate and establish tvDatafeed connection with credential fallback`
**Target files:** `src/stock_agent/pipelines/technical/core_data.py`
**Key signatures:**
- `get_tv_client()` returns `TvDatafeed(username, password)` when both `TV_USERNAME` and `TV_PASSWORD` are set; falls back to `TvDatafeed()` (anonymous) when either is empty
- Client creation is wrapped in `@lru_cache(maxsize=1)` to avoid redundant connections
**Acceptance criteria:** `get_tv_client()` called twice returns the same cached object; no credentials in `.env` still returns a valid client without raising.

---

### Step 17 — `feat: calculate baseline moving averages (50, 150, 200-day) using pandas-ta`
**Target files:** `src/stock_agent/pipelines/technical/indicators/moving_averages.py`
**Key signatures:**
- `def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame` — appends `SMA_50`, `SMA_150`, `SMA_200` columns using `pandas_ta.sma()`; returns mutated DataFrame
- `def calculate_52_week_levels(df: pd.DataFrame) -> tuple[float, float]` — returns `(high_52w, low_52w)` from the last 252 rows
**Acceptance criteria:** Output DataFrame contains all three SMA columns with no NaN in rows 200+; `calculate_52_week_levels` result satisfies `high_52w >= low_52w`.

---

## Phase 4: Advanced Technical Analysis Logic (Steps 18–24)

### Step 18 — `feat: build logic to verify current price position relative to moving averages`
**Target files:** `src/stock_agent/pipelines/technical/indicators/trend_setups.py`
**Key signatures:**
- `def price_above_mas(df: pd.DataFrame) -> bool` — returns `True` if latest close > `SMA_150` AND latest close > `SMA_200`
**Acceptance criteria:** Returns `False` when close equals `SMA_150`; returns `True` strictly above both.

---

### Step 19 — `feat: build logic to verify 200-day MA is trending upward (1 month minimum)`
**Target files:** `src/stock_agent/pipelines/technical/indicators/trend_setups.py`
**Key signatures:**
- `def ma200_trending_up(df: pd.DataFrame, lookback_days: int = 20) -> bool` — returns `True` if `SMA_200.iloc[-1] > SMA_200.iloc[-lookback_days]`
**Acceptance criteria:** Returns `False` when `SMA_200` is flat; returns `True` when last 20 values are strictly increasing.

---

### Step 20 — `feat: build logic to verify 50-day MA is above 150-day and 200-day MAs`
**Target files:** `src/stock_agent/pipelines/technical/indicators/trend_setups.py`
**Key signatures:**
- `def ma50_above_ma150_and_ma200(df: pd.DataFrame) -> bool` — returns `True` if `SMA_50.iloc[-1] > SMA_150.iloc[-1]` AND `SMA_50.iloc[-1] > SMA_200.iloc[-1]`
**Acceptance criteria:** All three conditions independently tested with edge-case DataFrames.

---

### Step 21 — `feat: implement MACD calculation and signal line`
**Target files:** `src/stock_agent/pipelines/technical/indicators/macd.py`
**Key signatures:**
- `def add_macd(df: pd.DataFrame) -> pd.DataFrame` — appends `MACD_12_26_9`, `MACDs_12_26_9`, `MACDh_12_26_9` columns using `pandas_ta.macd()`
**Acceptance criteria:** Output DataFrame contains all three MACD columns; no NaN in the last 100 rows of a 300-row input.

---

### Step 22 — `feat: implement volume analysis to detect dry-ups (below average volume)`
**Target files:** `src/stock_agent/pipelines/technical/indicators/trend_setups.py`
**Key signatures:**
- `def detect_volume_dryup(df: pd.DataFrame, lookback: int = 50, threshold: float = 0.7) -> bool` — returns `True` if latest volume < `threshold * mean(volume[-lookback:])`
**Acceptance criteria:** Returns `True` when latest volume is 60% of 50-day average; returns `False` when volume is at 80%.

---

### Step 23 — `feat: detect Volatility Contraction Pattern (VCP) via successive price tightening`
**Target files:** `src/stock_agent/pipelines/technical/indicators/trend_setups.py`
**Key signatures:**
- `def check_trend_template(df: pd.DataFrame) -> bool` — aggregates all Minervini conditions: `price_above_mas`, `ma200_trending_up`, `ma50_above_ma150_and_ma200`, close > `high_52w * 0.75`, close > `low_52w * 1.30`
- `def detect_vcp(df: pd.DataFrame, contractions: int = 3) -> bool` — splits last 60 bars into `contractions` windows; `True` if each successive window's price range is narrower than the previous
**Acceptance criteria:** `check_trend_template` returns `False` if any single condition fails; `detect_vcp` with monotonically narrowing ranges returns `True`.

---

### Step 24 — `feat: calculate final technical score (1-10) based on Trend Template and VCP`
**Target files:** `src/stock_agent/scoring/technical_scorer.py`
**Key signatures:**
- `INDICATOR_MODULES: dict[str, Callable]` — maps strategy string names to indicator functions, e.g. `{"trend_template": check_trend_template, "vcp": detect_vcp, "macd": add_macd, "moving_averages": add_moving_averages}`
- `def calculate_technical_score(df: pd.DataFrame, strategy: ScoringStrategy) -> TechnicalData` — dynamically imports only the indicator functions listed in `strategy.technical_indicators`; clamps score to `[1.0, 10.0]`
**Acceptance criteria:** A strategy with only `["trend_template"]` produces the same score regardless of VCP result; output `TechnicalData.score` is always in `[1.0, 10.0]`.

---

## Phase 5: Agent Assembly & CLI (Steps 25–30)

### Step 25 — `feat: initialize main PydanticAI Agent with system prompt and cloud model`
**Target files:** `src/stock_agent/agent.py`
**Key signatures:**
- `agent = Agent(model, result_type=StockReport, deps_type=AgentDependencies, system_prompt=SYSTEM_PROMPT)`
- `SYSTEM_PROMPT: str` — instructs the agent: "You are a financial analyst. ALL numerical data is pre-computed. Reason over the provided data only. NEVER estimate or calculate indicators yourself."
- `model` resolved from `settings.OPENAI_API_KEY` (OpenAI) or `settings.GEMINI_API_KEY` (Gemini) at startup
**Acceptance criteria:** `from stock_agent.agent import agent` imports cleanly; `agent.model` is not `None`.

---

### Step 26 — `feat: register fundamental and technical async tools to the agent`
**Target files:** `src/stock_agent/tools/fundamental_tools.py`, `src/stock_agent/tools/technical_tools.py`
**Key signatures:**
- `@agent.tool async def get_fundamental_data(ctx: RunContext[AgentDependencies], ticker: str) -> FundamentalData`
- `@agent.tool async def get_technical_data(ctx: RunContext[AgentDependencies], ticker: str) -> TechnicalData`
- `@agent.tool async def get_peer_reports(ctx: RunContext[AgentDependencies], ticker: str) -> list[PeerReport]`
- `@agent.tool async def get_moving_average_signal(ctx, ticker: str) -> dict`
- Ollama sub-agent instantiated **lazily** via `@lru_cache` — NOT at module import time:

```python
from functools import lru_cache

@lru_cache(maxsize=1)
def get_ollama_agent() -> Agent:
    # Lazy: only called on first tool invocation, not at import time
    return Agent(OllamaModel("llama3.2", base_url=settings.OLLAMA_HOST), result_type=NewsSummary)

@agent.tool
async def summarize_news_and_extract_risks(ctx, raw_articles: list[str]) -> NewsSummary:
    result = await get_ollama_agent().run(SUMMARIZE_PROMPT, deps=raw_articles)
    return result.data
```

**Acceptance criteria:** Module imports cleanly when Ollama is offline (lazy instantiation); `get_ollama_agent()` called twice returns the same cached object; the main cloud agent never receives raw article text.

---

### Step 27 — `feat: implement final weighted scoring pipeline (merging both scores)`
**Target files:** `src/stock_agent/agent.py`
**Key signatures:**
- `async def run_analysis(ticker: str, strategy: ScoringStrategy) -> StockReport` — constructs `AgentDependencies(strategy=strategy)`; calls `agent.run(prompt, deps=deps)`; returns `result.data`
- `prompt` includes the ticker and instructs the agent to call all registered tools before producing the `StockReport`
**Acceptance criteria:** `asyncio.run(run_analysis("AAPL", ScoringStrategy()))` with mocked tools returns a valid `StockReport` with `weighted_score` in `[1.0, 10.0]`.

---

### Step 28 — `feat: build interactive CLI for ticker input and weight configuration`
**Target files:** `src/stock_agent/main.py`
**Key signatures:**
- `def main()` — `argparse` with positional `ticker`, optional `--fundamental-weight` (default 0.5), `--technical-weight` (default 0.5), `--indicators` (nargs=`+`)
- Calls `asyncio.run(run_analysis(ticker, strategy))` and pretty-prints the `StockReport` as JSON
**Acceptance criteria:** `uv run python -m stock_agent.main AAPL --fundamental-weight 0.6 --technical-weight 0.4` parses correctly and dispatches the analysis.

---

### Step 29 — `feat: add FastAPI application with POST /analyze endpoint (synchronous path)`
**Target files:** `src/stock_agent/agent.py`
**Key signatures:**
- `app = FastAPI(title="Stock Agent API", lifespan=lifespan)`
- `POST /analyze` body: `AnalyzeRequest(ticker: str, strategy: ScoringStrategy)` → calls `run_analysis(...)` → returns `StockReport`
- This step creates the synchronous (non-Celery) version; Phase 9 will replace with async Celery dispatch
**Acceptance criteria:** `uvicorn stock_agent.agent:app` starts; `POST /analyze` with a mocked agent returns a valid `StockReport` JSON response.

---

### Step 30 — `feat: add peer stock analysis using yfinance industry peers`
**Target files:** `src/stock_agent/tools/fundamental_tools.py`, `src/stock_agent/pipelines/fundamental/yf_client.py`
**Key signatures:**
- `get_peer_reports` tool calls `fetch_industry_peers(ticker)` → runs `run_analysis(peer, strategy)` for each peer (max 5) concurrently via `asyncio.gather`
- Returns `list[PeerReport]` — only `ticker`, `weighted_score`, `recommendation` (not full `StockReport`)
**Acceptance criteria:** Peer analysis runs for at most 5 tickers; result is a list of `PeerReport` objects; confirmed with mocked `fetch_industry_peers`.

---

## Phase 6: Quality Assurance & Docs (Steps 31 is Phase 7 — see below)

*Note: Phase 6 testing steps are integrated into Phase 11 (Step 59). Phase 7 begins immediately after Phase 5.*

---

## Phase 7: NiceGUI Frontend (Steps 31–37)

### Step 31 — `chore: install nicegui and mount as fastapi sub-application`
**Target files:** `src/stock_agent/ui/app.py`, `pyproject.toml`
**Key signatures:**
- `uv add nicegui`
- `app = FastAPI()` imported from `agent.py`; `ui.run_with(app, port=settings.PORT)`
- `def create_app() -> FastAPI` — factory used by both CLI and UI entrypoints
**Acceptance criteria:** `uv run python -m stock_agent.ui.app` starts a NiceGUI server on the configured port with no errors.

---

### Step 32 — `feat: build main dashboard layout with ticker input and weight sliders`
**Target files:** `src/stock_agent/ui/app.py`, `src/stock_agent/ui/components/strategy_panel.py`
**Key signatures:**
- `ui.input(label="Ticker")` bound to a reactive string
- `ui.slider(min=0, max=100)` for fundamental/technical weights; values bound to a reactive `ScoringStrategy` instance
- Layout uses `ui.row`, `ui.column`, `ui.card` — no HTML/CSS
**Acceptance criteria:** User can type a ticker and adjust weights; state is reflected in a live `ScoringStrategy` object before any API call.

---

### Step 33 — `feat: implement async analysis trigger with real-time Redis progress polling`
**Target files:** `src/stock_agent/ui/app.py`, `src/stock_agent/ui/components/progress_panel.py`
**Key signatures:**
- `async def run_analysis()` — calls `POST /analyze` → receives `{"job_id": str}`
- `ui.timer(interval=0.5, callback=poll_progress)` — reads `GET /jobs/{job_id}/status` (Redis read) and updates `ui.linear_progress` and a status label
- Timer cancelled when `pct_complete == 100`
**Acceptance criteria:** Clicking "Analyze" dispatches a Celery task, never blocks the UI; progress panel updates every 500ms showing current `stage` and `pct_complete` from Redis; polling URL is `GET /jobs/{job_id}/status` (consistent with Steps 50 and 51).

---

### Step 34 — `feat: build StockReport display card with score gauges and recommendation badge`
**Target files:** `src/stock_agent/ui/components/report_card.py`
**Key signatures:**
- `def render_report(report: StockReport) -> None` — uses `ui.circular_progress` for `fundamental_score`, `technical_score`, `weighted_score`
- Color-coded `ui.badge` for `recommendation`: `green`=BUY, `yellow`=WATCH, `red`=AVOID
**Acceptance criteria:** A `StockReport` fixture renders all fields correctly with no runtime errors.

---

### Step 35 — `feat: build peer comparison table from PeerReport list`
**Target files:** `src/stock_agent/ui/components/peer_table.py`
**Key signatures:**
- `def render_peer_table(peers: list[PeerReport]) -> None` — uses `ui.aggrid` with columns: `Ticker`, `Score`, `Recommendation`; rows sortable by score descending
**Acceptance criteria:** A list of 5 mock `PeerReport` objects renders as a sortable table with no errors.

---

### Step 36 — `feat: implement ScoringStrategy configuration panel with dynamic metric toggles`
**Target files:** `src/stock_agent/ui/components/strategy_panel.py`
**Key signatures:**
- `ui.checkbox` for each available fundamental metric and technical indicator, driven by `AVAILABLE_METRICS: list[str]` constant in `config.py`
- Selection mutates the `ScoringStrategy` in place
**Acceptance criteria:** Toggling checkboxes updates `ScoringStrategy.fundamental_metrics` and `technical_indicators` lists reactively.

---

### Step 37 — `feat: apply dark theme and responsive layout polish`
**Target files:** `src/stock_agent/ui/theme.py`, `src/stock_agent/ui/app.py`
**Key signatures:**
- `DARK_PALETTE: dict[str, str]` — brand colors constant
- `ui.colors(**DARK_PALETTE)` applied at startup
- Layout uses `ui.splitter` for sidebar (strategy panel) + main content (report + peers)
**Acceptance criteria:** UI renders correctly in both desktop and mobile-width viewports; dark mode is active by default.

---

## Phase 8: Database & ORM (Steps 38–43)

### Step 38 — `chore: install sqlalchemy, alembic, asyncpg and configure database settings`
**Target files:** `pyproject.toml`, `src/stock_agent/config.py`
**Key signatures:**
- `uv add "sqlalchemy[asyncio]>=2" alembic asyncpg`
- Add to `Settings`: `DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/stockagent"`
- `alembic init migrations` — creates `migrations/` directory and `alembic.ini`
**Acceptance criteria:** `uv run alembic current` runs without error against a local Postgres instance.

---

### Step 39 — `feat: define StockReportRecord and AnalysisJobRecord SQLAlchemy ORM models`
**Target files:** `src/stock_agent/db/models.py`
**Key signatures:**
- `class Base(DeclarativeBase)` — shared metadata base
- `class AnalysisJobRecord(Base)` — `__tablename__ = "analysis_jobs"`; fields: `id: Mapped[UUID]` (pk, default `uuid4`), `ticker: Mapped[str]`, `status: Mapped[str]` (default `"pending"`), `created_at: Mapped[datetime]` (default `utcnow`)
- `class StockReportRecord(Base)` — `__tablename__ = "stock_reports"`; fields: `id: Mapped[UUID]`, `job_id: Mapped[UUID]` (FK → `analysis_jobs.id`), `ticker: Mapped[str]`, `weighted_score: Mapped[float]`, `recommendation: Mapped[str]`, `report_json: Mapped[dict]` (JSON column), `created_at: Mapped[datetime]`
**Acceptance criteria:** `python -c "from stock_agent.db.models import Base"` runs with no errors; both tables present in `Base.metadata.tables`.

---

### Step 40 — `feat: configure async SQLAlchemy engine, session factory, and FastAPI lifespan handler`
**Target files:** `src/stock_agent/db/session.py`
**Key signatures:**
- `engine = create_async_engine(settings.DATABASE_URL, echo=False)`
- `AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)`
- `async def get_db() -> AsyncGenerator[AsyncSession, None]` — FastAPI `Depends` dependency
- `@asynccontextmanager async def lifespan(app: FastAPI)` — calls `Base.metadata.create_all(engine)` on startup if `APP_ENV == "development"`
**Acceptance criteria:** FastAPI app starts without error; `GET /health` returns 200 after startup.

---

### Step 41 — `feat: create first alembic migration for job and report tables`
**Target files:** `migrations/versions/<hash>_create_job_report_tables.py`
**Key signatures:**
- `alembic revision --autogenerate -m "create job report tables"` — generates the migration
- Review generated `upgrade()` and `downgrade()` functions; ensure both tables are present
**Acceptance criteria:** `uv run alembic upgrade head` creates both tables in the Postgres database with no errors; `uv run alembic downgrade -1` removes them cleanly.

---

### Step 42 — `feat: implement async CRUD operations for saving and retrieving reports`
**Target files:** `src/stock_agent/db/crud.py`
**Key signatures:**
- `async def create_job(db: AsyncSession, ticker: str) -> AnalysisJobRecord`
- `async def update_job_status(db: AsyncSession, job_id: UUID, status: str) -> None`
- `async def save_report(db: AsyncSession, job_id: UUID, report: StockReport) -> StockReportRecord`
- `async def get_report_by_ticker(db: AsyncSession, ticker: str) -> StockReportRecord | None`
- `async def list_recent_jobs(db: AsyncSession, limit: int = 20) -> list[AnalysisJobRecord]`
**Acceptance criteria:** All five functions pass isolated unit tests using an in-memory SQLite async session.

---

### Step 43 — `feat: add GET /reports/{ticker} and GET /jobs FastAPI endpoints`
**Target files:** `src/stock_agent/agent.py` (or `src/stock_agent/api.py`)
**Key signatures:**
- `GET /reports/{ticker}` → calls `get_report_by_ticker(db, ticker)`; returns `StockReportRecord` or 404
- `GET /jobs` → calls `list_recent_jobs(db)`; returns `list[AnalysisJobRecord]`
- Both inject `AsyncSession` via `Depends(get_db)`
**Acceptance criteria:** Both endpoints return correct JSON with mocked DB session in unit tests; 404 is returned when ticker has no saved report.

---

## Phase 9: Distributed Workers & Real-Time State (Steps 44–52)

### Step 44 — `chore: install celery and redis client, configure broker and result backend`
**Target files:** `pyproject.toml`, `src/stock_agent/config.py`
**Key signatures:**
- `uv add "celery[redis]" redis`
- Add to `Settings`: `CELERY_BROKER_URL: str = "redis://localhost:6379/0"`, `CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"`, `REDIS_URL: str = "redis://localhost:6379/0"`, `OLLAMA_HOST: str = "http://localhost:11434"`
**Acceptance criteria:** `uv run celery -A stock_agent.worker.celery_app inspect ping` connects successfully to local Redis.

---

### Step 45 — `feat: create celery app instance with task routing and serialization config`
**Target files:** `src/stock_agent/worker/celery_app.py`
**Key signatures:**

```python
celery = Celery(
    "stock_agent",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery.conf.task_serializer = "json"
celery.conf.result_serializer = "json"
celery.conf.accept_content = ["json"]
celery.conf.task_routes = {"stock_agent.worker.tasks.*": {"queue": "analysis"}}
```

**Acceptance criteria:** `celery_app.py` imports cleanly; worker starts with `uv run celery -A stock_agent.worker.celery_app worker` without error.

---

### Step 46 — `feat: implement redis progress publisher utility`
**Target files:** `src/stock_agent/worker/state.py`
**Key signatures:**
- `def publish_progress(redis_client: Redis, job_id: str, stage: str, pct_complete: int, message: str) -> None` — writes `json.dumps({"stage": stage, "pct_complete": pct_complete, "message": message})` to Redis key `job:{job_id}:progress` with TTL of 600 seconds (10 minutes)
**Acceptance criteria:** Unit test verifies correct JSON written to a mock Redis under `job:{job_id}:progress`; a second call overwrites the previous value (no list accumulation); TTL is set on every write.

---

### Step 47 — `feat: implement run_fundamental_task celery task with redis progress updates`
**Target files:** `src/stock_agent/worker/tasks.py`
**Key signatures — sync wrapper delegates all async work via `asyncio.run()`:**

```python
@celery.task
def run_fundamental_task(job_id: str, ticker: str, strategy_dict: dict) -> dict:
    return asyncio.run(_async_run_fundamental(job_id, ticker, strategy_dict))

async def _async_run_fundamental(job_id: str, ticker: str, strategy_dict: dict) -> dict:
    # awaits yf_client and web_search
    # calls publish_progress(redis, job_id, ...) at 0%, 50%, 100%
    ...
    return fundamental_data.model_dump()
```

**Acceptance criteria:** Task runs in eager mode (`CELERY_TASK_ALWAYS_EAGER=True`); the `@celery.task` body contains **zero `await` calls**; Redis mock receives three progress events under `job:{job_id}:progress`; returns a valid serializable `FundamentalData` dict.

---

### Step 48 — `feat: implement run_technical_task celery task with redis progress updates`
**Target files:** `src/stock_agent/worker/tasks.py`
**Key signatures — same sync/async split pattern:**

```python
@celery.task
def run_technical_task(job_id: str, ticker: str, strategy_dict: dict) -> dict:
    return asyncio.run(_async_run_technical(job_id, ticker, strategy_dict))

async def _async_run_technical(job_id: str, ticker: str, strategy_dict: dict) -> dict:
    # awaits core_data.fetch_ohlcv() via asyncio.to_thread(); iterates strategy.technical_indicators
    # calls publish_progress(redis, job_id, ...) per indicator step
    ...
    return technical_data.model_dump()
```

**Acceptance criteria:** Task runs in eager mode; each indicator step publishes a distinct progress event to Redis under `job:{job_id}:progress`; the `@celery.task` body contains **zero `await` calls**.

---

### Step 49 — `feat: implement run_scoring_task as celery chord orchestrating both pipelines`
**Target files:** `src/stock_agent/worker/tasks.py`
**Key signatures — every `@celery.task` is synchronous; PydanticAI agent and DB writes bridged via `asyncio.run()`:**

```python
@celery.task
def run_scoring_task(job_id: str, ticker: str, strategy_dict: dict) -> None:
    chord(
        group(
            run_fundamental_task.s(job_id, ticker, strategy_dict),
            run_technical_task.s(job_id, ticker, strategy_dict),
        ),
        merge_and_score.s(job_id, ticker, strategy_dict),
    ).delay()

@celery.task
def merge_and_score(pipeline_results: list[dict], job_id: str, ticker: str, strategy_dict: dict) -> dict:
    return asyncio.run(_async_merge_and_score(pipeline_results, job_id, ticker, strategy_dict))

async def _async_merge_and_score(
    pipeline_results: list[dict], job_id: str, ticker: str, strategy_dict: dict
) -> dict:
    async with AsyncSessionLocal() as db:
        # awaits agent.run(...) with AgentDependencies injected
        # awaits crud.save_report(db, ...)
        # publishes final 100% progress to job:{job_id}:progress
        ...
        return report.model_dump()
```

**Acceptance criteria:** Full end-to-end test (mocked pipelines, mocked PydanticAI agent, mock `AsyncSessionLocal`) produces a saved `StockReportRecord` and a final Redis `job:{job_id}:progress` at 100%; **no `await` appears in any `@celery.task`-decorated function body**; `_async_merge_and_score` uses `async with AsyncSessionLocal() as db:` and **never** uses `Depends(get_db)`.

---

### Step 50 — `feat: add POST /analyze FastAPI endpoint that dispatches the celery scoring task`
**Target files:** `src/stock_agent/agent.py` (or `src/stock_agent/api.py`)
**Key signatures:**
- `POST /analyze` body: `AnalyzeRequest(ticker: str, strategy: ScoringStrategy)` → calls `create_job(db, ticker)` to get a stable `job_id` → calls `run_scoring_task.delay(str(job_id), ticker, strategy.model_dump())` → returns `{"job_id": str}` only
- The Celery `task_id` is intentionally **not** returned — the UI uses `job_id` exclusively
**Acceptance criteria:** Unit test with mocked Celery confirms `run_scoring_task.delay` is called with the correct `job_id` as first argument; response body contains `job_id` and no `task_id`.

---

### Step 51 — `feat: add GET /jobs/{job_id}/status endpoint that reads progress from redis`
**Target files:** `src/stock_agent/agent.py` (or `src/stock_agent/api.py`)
**Key signatures:**
- `GET /jobs/{job_id}/status` → reads `job:{job_id}:progress` from Redis
- Returns the parsed JSON progress object, or `{"stage": "pending", "pct_complete": 0, "message": ""}` if key is not yet set
**Acceptance criteria:** Unit test with mock Redis confirms correct progress object returned; missing key returns the pending default; key pattern `job:{job_id}:progress` is consistent with `publish_progress` in Step 46.

---

### Step 52 — `chore: write docker-compose.yml with five services: app, worker, redis, postgres, ollama`
**Target files:** `docker-compose.yml`
**Key services:**
- `app` — NiceGUI+FastAPI; `depends_on: [redis, postgres, ollama]`; `env_file: .env`; volume mount for hot reload
- `worker` — same image as `app`; `command: celery -A stock_agent.worker.celery_app worker --loglevel=info`; env `OLLAMA_HOST=http://ollama:11434`
- `redis` — `redis:7-alpine`
- `postgres` — `postgres:16-alpine`; `POSTGRES_DB=stockagent`; persistent named volume `postgres_data:/var/lib/postgresql/data`
- `ollama` — `ollama/ollama`; persistent named volume `ollama_data:/root/.ollama`; `ports: ["11434:11434"]`

**Critical:** Worker container connects to Ollama via service name `http://ollama:11434`, NOT `localhost` — `localhost` inside the container points to the container itself.

**Acceptance criteria:** `docker-compose up --build` starts all five services; `docker-compose ps` shows all five as healthy; `docker exec <worker> celery inspect ping` succeeds; worker logs show successful Ollama connection.

---

## Phase 10: Production & Deployment (Steps 53–59)

### Step 53 — `chore: write multi-stage Dockerfile for production image`
**Target files:** `Dockerfile`
**Key:**
- Stage 1 (`builder`) — `FROM python:3.12-slim`; `uv sync --frozen --no-dev`; builds venv
- Stage 2 (`runtime`) — copies only the venv and `src/`; `COPY src/ ./src/` — this pattern inherently excludes `scripts/` (at repo root, never inside `src/`); runs as non-root user `appuser`; `EXPOSE ${PORT}`
**Acceptance criteria:** `docker build -t stock-agent .` completes without errors; image size is under 500MB; `scripts/` directory is NOT present in the built image (`docker run stock-agent ls /app/scripts` returns non-zero).

---

### Step 54 — `feat: implement /health and /ready FastAPI endpoints`
**Target files:** `src/stock_agent/agent.py` (or `src/stock_agent/api.py`)
**Key signatures:**
- `GET /health` → `{"status": "ok", "version": settings.APP_VERSION}`
- `GET /ready` → checks tvDatafeed connectivity, yfinance reachability, and Ollama connectivity via `GET http://ollama:11434/api/tags`; returns `{"status": "ready"}` (200) or `{"status": "unavailable", "reason": str}` (503)
**Acceptance criteria:** Both endpoints return correct status codes in unit tests with mocked dependencies; `/ready` correctly returns 503 when Ollama mock raises a connection error.

---

### Step 55 — `feat: add structured JSON logging with logfire for latency and cost tracking`
**Target files:** `src/stock_agent/config.py`, `src/stock_agent/agent.py`
**Key signatures:**
- `logfire.configure(token=settings.LOGFIRE_TOKEN)` called in app startup
- `logfire.instrument_pydantic_ai(agent)` wraps every agent run
- Each tool call logs `ticker: str`, `duration_ms: float`, `token_usage: dict`
**Acceptance criteria:** `uv run python -m stock_agent.main AAPL` produces structured JSON log output with timing data visible in terminal.

---

### Step 56 — `chore: add ruff to dev dependencies and write GitHub Actions CI workflow`
**Target files:** `.github/workflows/ci.yml`, `pyproject.toml`
**Key:**
- `uv add --dev ruff` adds linter to dev dependencies **in the same commit**
- CI triggers on `pull_request` to `main`
- Steps: `actions/checkout`, `uv sync`, `uv run ruff check .`, `uv run pytest --cov --cov-fail-under=70`
**Acceptance criteria:** `ruff` appears in `[tool.uv.dev-dependencies]` in `pyproject.toml`; a failing test blocks the PR merge; a passing PR shows a green checkmark.

---

### Step 57 — `chore: write GitHub Actions CD workflow (Docker build and ECR push on main)`
**Target files:** `.github/workflows/cd.yml`
**Key:**
- Triggers on `push` to `main`
- Steps: `aws-actions/configure-aws-credentials@v4`, `aws-actions/amazon-ecr-login@v2`, `docker build -t $ECR_REPOSITORY:$GITHUB_SHA .`, `docker push $ECR_REPOSITORY:$GITHUB_SHA`
- Uses GitHub Secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `ECR_REPOSITORY`
**Acceptance criteria:** Merging to `main` triggers the workflow; the image tag `$GITHUB_SHA` appears in the AWS ECR console.

---

### Step 58 — `feat: write .env.example and secrets management guide`
**Target files:** `.env.example`, `docs/deployment.md`
**Key:**
- `.env.example` contains all keys from Section 7 of `CLAUDE.md`, including `OLLAMA_HOST=http://ollama:11434` (Docker) or `http://localhost:11434` (local dev); all secret values replaced with `<YOUR_VALUE_HERE>`
- `docs/deployment.md` explains AWS Secrets Manager integration and Ollama model pre-pull requirement (`ollama pull llama3.2`)
**Acceptance criteria:** A new developer can clone the repo, copy `.env.example` to `.env`, fill in values, and run `docker-compose up --build` successfully on first try.

---

### Step 59 — `docs: author comprehensive README with architecture diagram, setup guide, and CI badge`
**Target files:** `README.md`
**Key:**
- Mermaid architecture diagram showing full data flow: `User → NiceGUI → FastAPI → Celery → [Fundamental Pipeline | Technical Pipeline] → Redis → NiceGUI`
- Installation steps: `git clone`, `uv sync`, CLI usage, Docker usage
- Note about Ollama model pre-pull (`docker exec ollama ollama pull llama3.2`)
- CI badge from `.github/workflows/ci.yml`
- Live demo link placeholder
**Acceptance criteria:** README renders correctly on GitHub with a working CI badge and a copy-pasteable quickstart command.

---

## Phase 11: Stress Testing & Dev Tools (Steps 60–62)

### Step 60 — `feat: create stress_test.py script to dispatch 10+ concurrent celery jobs`
**Target files:** `scripts/stress_test.py` — at the **repo root**, NOT inside `src/`; excluded from the production image by the `COPY src/ ./src/` pattern in the Dockerfile

**Key signatures — single `asyncio.run()` for the entire batch:**

```python
STRESS_TEST_TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "AMD", "NFLX", "PLTR"]

def run_stress_test(strategy: ScoringStrategy) -> list[str]:
    """Synchronous entry point. One event loop for all DB job creation."""
    return asyncio.run(_async_create_all_jobs(strategy))

async def _async_create_all_jobs(strategy: ScoringStrategy) -> list[str]:
    async with AsyncSessionLocal() as db:
        jobs = await asyncio.gather(
            *[create_job(db, ticker) for ticker in STRESS_TEST_TICKERS]
        )
    for job in jobs:
        run_scoring_task.delay(str(job.id), job.ticker, strategy.model_dump())
    return [str(job.id) for job in jobs]
```

**Acceptance criteria:** Script dispatches exactly 10 Celery tasks; all 10 DB jobs created in a **single event loop** (not 10 separate `asyncio.run()` calls); verified in unit test with mocked `AsyncSessionLocal` and `run_scoring_task.delay`.

---

### Step 61 — `feat: add POST /dev/stress-test FastAPI endpoint guarded by APP_ENV check`
**Target files:** `src/stock_agent/agent.py` (or `src/stock_agent/api.py`)
**Key signatures:**

```python
@router.post("/dev/stress-test", include_in_schema=False)
def trigger_stress_test(strategy: ScoringStrategy, settings: Settings = Depends(get_settings)):
    if settings.APP_ENV != "development":
        raise HTTPException(status_code=403, detail="Dev tools disabled in production")
    job_ids = run_stress_test(strategy)
    return {"job_ids": job_ids}
```

**Acceptance criteria:** Returns 403 when `APP_ENV=production`; returns a list of 10 `job_id`s when `APP_ENV=development`; endpoint excluded from OpenAPI docs (`include_in_schema=False`).

---

### Step 62 — `feat: add dev tools panel to NiceGUI with 10 concurrent live progress bars`
**Target files:** `src/stock_agent/ui/components/dev_tools.py`, `src/stock_agent/ui/app.py`
**Key signatures:**
- `def render_dev_tools(settings: Settings) -> None` — only called when `settings.APP_ENV == "development"`; rendered as `ui.expansion("Dev Tools")`
- On button click: `POST /dev/stress-test` → receives `{"job_ids": list[str]}`
- Dynamically creates 10 rows of `(ticker_label, ui.linear_progress, ui.label)` bound to individual `ui.timer` instances polling `GET /jobs/{job_id}/status` every 500ms
- All 10 timers run concurrently — proves NiceGUI event loop is non-blocking under load
- Each timer cancels itself when `pct_complete == 100`

**Acceptance criteria:** Clicking the stress test button renders 10 progress bars that update independently and asynchronously; UI remains fully interactive during the test (ticker input still responds); all 10 timers cancel cleanly on completion.

---

*End of protocol. 62 steps. 11 phases. Build in order.*
