# Architecture & Data Flow Diagrams

A living document describing the data flows and component interactions of the Autonomous PydanticAI Stock Analyst Agent.
Updated as each phase is built. All diagrams use [Mermaid](https://mermaid.js.org/) and render natively on GitHub.

---

## FastAPI Server Lifecycle (`lifespan`)

The FastAPI app uses an `@asynccontextmanager` lifespan hook to manage resources that must be initialized before the server accepts any requests and torn down cleanly on shutdown.

```
server process starts
        │
        ▼
 ┌─ lifespan STARTUP ──────────────────────────────────┐
 │  • async SQLAlchemy engine created                  │
 │  • DB connection pool warmed up                     │
 │  • Tables auto-created if APP_ENV == "development"  │
 └─────────────────────────────────────────────────────┘
        │
        ▼
 server is reachable — clients can POST /analyze
        │
        ▼
 ┌─ lifespan SHUTDOWN ─────────────────────────────────┐
 │  • engine.dispose() — all DB connections closed     │
 │  • Redis connections released                       │
 └─────────────────────────────────────────────────────┘
        │
        ▼
server process exits
```

**Why lifespan over `@app.on_event("startup")`:** `on_event` is deprecated in FastAPI 0.93+. The `lifespan` context manager is the current standard — it co-locates startup and shutdown logic, and works correctly with pytest's `AsyncClient` test fixture.

**Defined in:** `src/stock_agent/db/session.py` (Step 40) — imported and passed to `FastAPI(lifespan=lifespan)` in `api.py`.

**Module ownership:** The FastAPI app, lifespan hook, all request models, and every route handler live exclusively in `src/stock_agent/api.py`. No route definitions exist in any other module. This keeps a clean separation:

| Module | Responsibility |
|---|---|
| `agent.py` | PydanticAI agent, tool registration, `run_analysis()` |
| `api.py` | FastAPI app, lifespan, request models, all route handlers |
| `main.py` | CLI — argparse, `asyncio.run()` |

---

## Phase 2 — Fundamental Data Pipeline

### Web Search Flow (`web_search.py`)

How a single ticker input becomes a rich set of deduplicated, categorised news snippets.

```mermaid
flowchart TD
    A([User: ticker + company_name]) --> B[search_recent_catalysts]
    A --> C[search_risk_news]

    subgraph Catalysts ["search_recent_catalysts — 5 concurrent queries"]
        B --> B1["① earnings & revenue guidance"]
        B --> B2["② shares offering & dilution"]
        B --> B3["③ acquisitions & mergers"]
        B --> B4["④ govt contracts & partnerships"]
        B --> B5["⑤ IR press releases"]
    end

    subgraph Risks ["search_risk_news — 3 concurrent queries"]
        C --> C1["① lawsuit & SEC investigation"]
        C --> C2["② fraud, recall, fine, penalty"]
        C --> C3["③ bankruptcy & debt risk"]
    end

    B1 & B2 & B3 & B4 & B5 -->|"asyncio.gather()\n5 snippets each\n= up to 25 raw"| D[_deduplicate]
    C1 & C2 & C3 -->|"asyncio.gather()\n5 snippets each\n= up to 15 raw"| E[_deduplicate]

    D -->|unique catalyst snippets| F([list of str])
    E -->|unique risk snippets| G([list of str])
```

**Key design decisions:**
- `asyncio.gather()` fires all queries concurrently — no sequential blocking
- Each query uses `asyncio.to_thread()` internally to offload the blocking DuckDuckGo HTTP call to a thread pool, keeping the event loop free
- `max_results=5` per query — keeps each query focused; avoids generic coverage drowning out specific signals
- `_deduplicate()` removes snippets that appear in multiple query results (e.g. a major earnings event surfaces across several queries simultaneously) — prevents the downstream Ollama NLP agent from wasting context window tokens on repeated information
- Current year injected via `datetime.now().year` — never hardcoded — ensures results are always recent

---

---

## Phase 2 — Fundamental Scoring Pipeline

### Scoring Algorithm Flow (`fundamental_scorer.py`)

How a `FundamentalData` object and `ScoringStrategy` become a single score in `[1.0, 10.0]`.

```mermaid
flowchart TD
    A([FundamentalData + ScoringStrategy]) --> B

    subgraph Step1 ["Step 1 — Sub-score per active metric (0.0 → 1.0)"]
        B[For each metric in strategy.fundamental_metrics]
        B --> C1["pe_ratio → lower is better\nP/E 15 ≈ 0.80 | P/E 50 ≈ 0.30 | None = 0.0"]
        B --> C2["revenue_growth → higher is better\n+50% ≈ 0.90 | negative ≈ 0.10"]
        B --> C3["market_cap → higher is better\nlarge cap = stability signal"]
        B --> C4["beta → closer to 1.0 is neutral\nbeta > 2 penalised as excess risk"]
    end

    subgraph Step2 ["Step 2 — Re-normalise weights of active metrics"]
        C1 & C2 & C3 & C4 --> D["Fetch base weights from METRIC_WEIGHTS in config.py"]
        D --> E["Re-normalise: weight / sum of active weights\n→ active weights always sum to 1.0"]
    end

    subgraph Step3 ["Step 3 — Weighted sum → scale → clamp"]
        E --> F["weighted_sum = Σ sub_score × normalised_weight\n→ float in 0.0 to 1.0"]
        F --> G["Scale: final = 1.0 + weighted_sum × 9.0\n→ float in 1.0 to 10.0"]
        G --> H["Clamp to 1.0–10.0\n← safety net"]
    end

    H --> I([fundamental_score: float])
```

**Why re-normalise weights?**
If a strategy only activates `pe_ratio` (base weight 0.4), re-normalising it to `1.0` ensures the score still spans the full `[1.0, 10.0]` range. Without re-normalisation, the maximum possible score would be artificially capped at `1.0 + 0.4 × 9.0 = 4.6` — penalising focused strategies unfairly.

**Sub-score vs weight — two independent concerns:**
- **Sub-score** answers: *"how good is this metric's value?"* → always `0.0` to `1.0`
- **Weight** answers: *"how much do we care about this metric?"* → re-normalised to sum to `1.0`

The raw value (e.g. P/E = 15) never flows through to the final score directly — it is always converted to a sub-score first.

---

---

## Phase 3 & 4 — Technical Data Pipeline

### Full Technical Pipeline Flow

How a ticker symbol becomes a `TechnicalData` object with a score in `[1.0, 10.0]`.

```mermaid
flowchart TD
    A([ticker: str]) --> B

    subgraph Fetch ["core_data.py — Fetch & Validate"]
        B["fetch_ohlcv(ticker)\nasyncio.to_thread → _fetch_history (lru_cache)"]
        B --> C["validate_ohlcv(df)\n• check required columns\n• ffill().bfill() NaN\n• raise ValueError if rows < 200"]
    end

    C --> D

    subgraph Enrich ["indicators/ — Enrich DataFrame (Chain of Responsibility)"]
        D["add_moving_averages(df)\n→ appends SMA_50, SMA_150, SMA_200"]
        D --> E["add_macd(df)  ← only if 'macd' in strategy\n→ appends MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9"]
        E --> F["calculate_52_week_levels(df)\n→ returns (high_52w, low_52w) from last 252 rows"]
    end

    F --> G

    subgraph Checks ["trend_setups.py — Boolean Signals"]
        G["price_above_mas(df)\nclose > SMA_150 AND close > SMA_200"]
        G --> H["ma200_trending_up(df)\nSMA_200 today > SMA_200 20 days ago"]
        H --> I["ma50_above_ma150_and_ma200(df)\nSMA_50 > SMA_150 AND SMA_50 > SMA_200"]
        I --> J["check_trend_template(df)\nAll 5 Minervini conditions — True only if ALL pass"]
        I --> K["detect_vcp(df)\n60 bars → 3 windows → each range strictly narrower"]
        I --> L["detect_volume_dryup(df)\nlatest volume < 70% of 50-day average"]
    end

    J & K & L --> M

    subgraph Score ["technical_scorer.py — Score"]
        M["Active indicators from strategy.technical_indicators\nbool → 1.0 / 0.0 per indicator"]
        M --> N["Re-normalise INDICATOR_WEIGHTS\nso active weights always sum to 1.0"]
        N --> O["weighted_sum = Σ signal × normalised_weight\n→ 0.0 to 1.0"]
        O --> P["Scale: 1.0 + weighted_sum × 9.0\nClamp to 1.0–10.0"]
    end

    P --> Q([TechnicalData\nsma_50, sma_150, sma_200\nhigh_52w, low_52w\ntrend_template_passed, vcp_detected\nscore: float])
```

---

### Chain of Responsibility — DataFrame Enrichment

Each module appends its columns and passes the same DataFrame forward. No module fetches data independently — all read from the single enriched object.

```
fetch_ohlcv()                    → Open, High, Low, Close, Volume
  → add_moving_averages()        → + SMA_50, SMA_150, SMA_200
      → add_macd()               → + MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
          → boolean checks       →   read all columns above, return True/False
              → calculate_technical_score()  → TechnicalData with score
```

**Why this pattern:**
- No module needs to know where prior columns came from
- Nothing is fetched or computed twice
- Adding a new indicator = add a new module, append to the chain — no other file changes

---

### `lru_cache` on `_fetch_history`

`_fetch_history` is decorated with `@lru_cache(maxsize=128)`. It is the only function cached because:
1. It is the sole source of blocking HTTP I/O — caching at this layer prevents all redundant network calls
2. `lru_cache` requires a plain `def` — it cannot wrap `async def` functions

The cache is **process-level** (shared across all users for the lifetime of the server process). Primary use case: peer analysis runs where the same ticker may be requested multiple times within a single analysis. Production upgrade path: replace with `cachetools.TTLCache` to add staleness expiry.

---

### Technical Scoring — Weight Re-normalisation

Mirrors the fundamental scorer's approach. Only indicators listed in `strategy.technical_indicators` are active. Their base weights (from `INDICATOR_WEIGHTS` in `config.py`) are re-normalised so they always sum to 1.0:

```
Default INDICATOR_WEIGHTS:
  trend_template: 0.5
  vcp:            0.3
  macd:           0.1
  moving_averages: 0.1

Strategy: ["trend_template", "vcp"] only
  active total = 0.5 + 0.3 = 0.8
  re-normalised:
    trend_template: 0.5 / 0.8 = 0.625
    vcp:            0.3 / 0.8 = 0.375
                               ──────
                                1.000 ✓
```

A strategy with only `["trend_template"]` produces the same score regardless of VCP result — VCP is not in scope, its weight is zero.

---

---

## Phase 5 — Agent Assembly & Tool Registration

### Tool Registration Flow

How `@agent.tool` decorators wire tools onto the agent at import time, and why imports are deferred to the bottom of `agent.py`.

```mermaid
flowchart TD
    A([Python imports stock_agent.agent]) --> B["agent.py top: _resolve_model()"]
    B --> C["agent = Agent(model, output_type=StockReport, deps_type=AgentDependencies)"]
    C --> D["import stock_agent.tools.fundamental_tools"]
    C --> E["import stock_agent.tools.technical_tools"]

    D --> D1["@agent.tool — get_fundamental_data"]
    D --> D2["@agent.tool — get_peer_reports"]
    D --> D3["@agent.tool — summarize_news_and_extract_risks"]

    E --> E1["@agent.tool — get_technical_data"]
    E --> E2["@agent.tool — get_moving_average_signal"]

    D1 & D2 & D3 & E1 & E2 --> F([agent._function_toolset — 5 tools registered])
```

**Why imports are at the bottom of `agent.py`:**
Tool files import `agent` from `agent.py`. If `agent.py` also imported tool files at the top, Python would try to import the tool files before `agent` was defined — circular import. Bottom-of-file imports defer the tool registration until after `agent` exists in memory.

---

### Agent Run — Tool Call Flow

How the cloud LLM calls tools during a single `agent.run()` invocation.

```mermaid
sequenceDiagram
    participant User
    participant Agent as Cloud Agent (OpenAI/Gemini)
    participant FT as fundamental_tools.py
    participant TT as technical_tools.py
    participant Ollama as Ollama Sub-Agent (llama3.2)
    participant Pipeline as Pipeline (yfinance + pandas-ta)

    User->>Agent: agent.run("Analyse ONDS", deps=AgentDependencies(strategy))

    Agent->>TT: get_technical_data("ONDS")
    TT->>Pipeline: fetch_ohlcv → calculate_technical_score
    Pipeline-->>TT: TechnicalData (sma_50, vcp, score)
    TT-->>Agent: TechnicalData

    Agent->>FT: get_fundamental_data("ONDS")
    FT->>Pipeline: fetch_valuation_metrics + fetch_earnings_growth
    Pipeline-->>FT: raw metrics dict
    FT-->>Agent: FundamentalData (pe_ratio, score)

    Agent->>FT: summarize_news_and_extract_risks("ONDS", "Ondas Holdings")
    FT->>Pipeline: search_recent_catalysts + search_risk_news (concurrent)
    Pipeline-->>FT: raw article snippets
    FT->>Ollama: prompt + articles (cloud agent never sees raw text)
    Ollama-->>FT: NewsSummary (summary, risk_flags)
    FT-->>Agent: NewsSummary

    Note over Agent: Optionally calls get_moving_average_signal<br/>if it needs to verify specific MA values

    Agent-->>User: StockReport (ticker, scores, recommendation, summary, peers)
```

**Key architectural constraint:**
The cloud agent receives only structured, pre-computed outputs — `TechnicalData`, `FundamentalData`, `NewsSummary`. Raw article text, OHLCV DataFrames, and intermediate calculations never appear in the cloud model's context window.

---

### Heavy vs Lightweight Tool — Decision Boundary

```
get_technical_data("ONDS")          ← Heavy: full pipeline, called once
  ↓
TechnicalData(trend_template=False, score=4.0)

Agent reasoning: "Why did trend_template fail? Is it a near-miss or a real breakdown?"

get_moving_average_signal("ONDS")   ← Lightweight: one fetch + one calculation
  ↓
{price: 10.75, sma_50: 10.99}       ← 2.2% below SMA-50 = near-miss

Agent conclusion: "Near-miss on trend template — not a structural breakdown."
```

Without the lightweight tool, the agent re-runs the full pipeline or reasons blindly from the boolean.

---

*More diagrams will be added as phases are built.*
