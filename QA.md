# Project Q&A Log

Running record of design and concept questions discussed during development.

---

## Question Index

| # | Question (short) | Phase / Topic |
|---|---|---|
| 1 | Why no `ge=0.0` on `pe_ratio`, `revenue_growth`, `beta`? | Core Schemas |
| 2 | Can beta be negative? What does negative beta mean? | Core Schemas |
| 3 | If beta is 2, does the stock go down 2x? | Core Schemas |
| 4 | Why is `AgentDependencies` a dataclass holding `ScoringStrategy`? | Architecture |
| 5 | Why not pass fundamental data in the agent context? | Architecture |
| 6 | Why should agent tools be thin? Why delegate calculations to utils? | Architecture |
| 7 | Why add `Field(description=...)` to every Pydantic model field? | Architecture |
| 8 | Why use `BaseSettings` over a plain settings class? | Configuration |
| 9 | What can `SettingsConfigDict` be used for beyond `.env`? | Configuration |
| 10 | Risk of blocking calls inside `async def`; how `asyncio.to_thread()` solves it | Async/Threading |
| 11 | How does OHLCV data cleaning work and why is it critical? | Technical Data |
| 12 | Why drop tvdatafeed and use yfinance for OHLCV? | Technical Data |
| 13 | What about scraping TradingView charts with a vision model? | Technical Data |
| 14 | How do we get the full company name from a ticker symbol? | Fundamental Pipeline |
| 15 | How do we ensure news search returns relevant catalysts, not generic coverage? | Fundamental Pipeline |
| 16 | Is `extract_risk_flags()` a guardrails system? Does Celery call it directly? | Fundamental Pipeline |
| 17 | When to enforce rules in Python vs. rely on LLM reasoning? | Fundamental Pipeline |
| 18 | How does the fundamental scoring algorithm work? | Fundamental Pipeline |
| 19 | Where does the 50% weight come from? What do `1` and `9` mean in the scaling formula? | Fundamental Pipeline |
| 20 | What happens when yfinance returns an empty industry peers list? | Fundamental Pipeline |
| 21 | Why is `_fetch_history` decorated with `@lru_cache`? | Technical Pipeline |
| 22 | What is `cachetools.TTLCache` and when to use it instead of `lru_cache`? | Technical Pipeline |
| 23 | Where does `price_above_mas` get its SMA data? Does it make a separate fetch? | Technical Pipeline |
| 24 | What does `price_above_mas` check and why does it matter? | Technical Pipeline |
| 25 | What are the five Minervini Trend Template conditions and why must every one pass? | Technical Pipeline |
| 26 | What is the VCP and how does `detect_vcp` measure it? | Technical Pipeline |
| 27 | Why does `get_moving_average_signal` exist as a separate tool? | Agent Tools |
| 28 | How does PydanticAI tool registration work? What does `@agent.tool` do? | Agent Tools |
| 29 | Why are tool modules imported at the bottom of `agent.py`? | Agent Tools |
| 30 | Why is the Ollama sub-agent lazy-initialised with `@lru_cache`? | Agent Tools |
| 31 | Why does pydantic-ai connect to Ollama via `OpenAIProvider`? | Agent Tools |
| 32 | How do you test a PydanticAI agent without a real API key? | Testing |
| 33 | What should the frontend display when `pe_ratio` is `None`? | UI |
| 34 | Why is `main.py` inside `src/stock_agent/` instead of the project root? | Project Structure |
| 35 | Is there a size limit on `CLAUDE.md`? When should it be split? | Project Structure |
| 36 | Why is `db.refresh()` called after every commit in the CRUD layer? | Database |
| 37 | Why does `save_report` store scores in both `report_json` and dedicated columns? | Database |
| 38 | Why do we have a dedicated CRUD layer instead of writing DB calls inline? | Database |
| 39 | What is `aiosqlite` and why does it eliminate the need for Docker in DB tests? | Database / Testing |
| 40 | Why does `save_report` convert scores via `Decimal(str(round(score, 1)))` — why go through `str()`? | Database |

---

## Phase 1 — Core Schemas

### Q: Why does `FundamentalData` not apply `ge=0.0` to `pe_ratio`, `revenue_growth`, and `beta`?
`market_cap` and `score` correctly have `ge=0.0`. `pe_ratio` and `revenue_growth` are left unconstrained because they can legitimately be negative (e.g. a company losing money has negative earnings, negative revenue growth in a down quarter). `beta` is also left unconstrained — see next entry.

---

### Q: Can beta be negative? What does a negative beta mean?
Yes. Beta measures an asset's sensitivity to market moves. A negative beta means the asset moves **inversely** to the market. Examples: gold ETFs, inverse ETFs, some defensive instruments. So leaving `beta: float | None` without `ge=0.0` is intentional and correct.

---

### Q: If beta is 2, does that mean the stock goes down 2x if the market goes down?
Yes — beta measures sensitivity in **both directions**:
- **Beta = 2** → stock moves ~2x the market (market -5% → stock ~-10%; market +5% → stock ~+10%)
- **Beta = 1** → moves 1:1 with the market
- **Beta = 0.5** → half the market's volatility
- **Beta = 0** → uncorrelated (e.g. cash)
- **Beta = -1** → moves opposite the market

High-beta stocks (>1.5) tend to be high-growth/speculative (TSLA, NVDA). Low-beta stocks (<0.5) tend to be defensives (utilities, consumer staples). In this agent, beta feeds into `FundamentalData` as a risk signal.

---

## Phase 1 — Architecture & Design

### Q: Why is `AgentDependencies` a dataclass that holds a `ScoringStrategy`? Is it the context passed to the PydanticAI agent?
Yes — `AgentDependencies` is the **dependency injection container** PydanticAI passes to every tool call via `ctx.deps`. When you call `agent.run(prompt, deps=AgentDependencies(strategy=my_strategy))`, every `@agent.tool` can access `ctx.deps.strategy` to know how to compute scores.

It's a `@dataclass` (not a `BaseModel`) because it's a runtime carrier, not a data model you validate or serialize. As the project grows it could also carry a DB session or Redis client — anything tools need that isn't part of the LLM prompt.

---

### Q: Why not pass the fundamental data of a ticker in the context as well? The agent needs the full picture to make decisions.
The agent doesn't receive pre-fetched data in the context — it **calls tools to fetch data itself**. The flow is:

```
agent.run(prompt, deps=AgentDependencies(strategy=strategy))
    → agent calls get_fundamental_data("AAPL")  → FundamentalData
    → agent calls get_technical_data("AAPL")    → TechnicalData
    → agent calls get_peer_reports("AAPL")      → list[PeerReport]
    → agent reasons over all results → StockReport
```

The `ScoringStrategy` lives in deps because it's **configuration** (how to compute scores), not data. Passing pre-fetched data in deps would remove the agent's ability to decide which tools to call and in what order — that's the agentic behavior we want.

**Rule of thumb:** context injection should be dynamic values that come from user choices — in our case, the ticker and weights.

---

### Q: Why should agent tools be focused/thin? Why delegate heavy calculations to util functions?
**Separation of concerns** — tools are thin orchestrators, not calculators:

```python
@agent.tool
async def get_fundamental_data(ctx: RunContext[AgentDependencies], ticker: str) -> FundamentalData:
    data = await fetch_valuation_metrics(ticker)        # util does the fetching
    return calculate_fundamental_score(data, ctx.deps.strategy)  # scorer does the math
```

Reasons:
1. **Testability** — util functions can be unit tested in complete isolation without invoking the agent or mocking PydanticAI
2. **Reusability** — the same util is called by both the agent tool AND the Celery worker task (no duplication)
3. **Non-negotiable rule** — all numerical calculations must be done by the deterministic pipeline before the LLM is invoked; heavy logic inside tools would blur this boundary
4. **Debuggability** — bugs are immediately locatable: data fetching layer, calculation layer, or agent reasoning layer
5. **Swappability** — scoring algorithm or data source can be swapped without touching the tool interface

The LLM only ever sees **clean, typed, pre-computed results**.

---

### Q: Why should we add `Field(description=...)` to every Pydantic model field? Is it necessary?
Yes — descriptions serve double duty:

1. **For the LLM** — PydanticAI serializes the full model schema (including field descriptions) into the agent's context. Without descriptions the agent just sees raw numbers; with them it understands *what* each value represents and reasons over it more accurately.
2. **For OpenAPI docs** — descriptions appear automatically in `/docs`, making the API self-documenting at zero extra cost.

Without descriptions:
```json
{"pe_ratio": 15.2, "score": 7.5}
```
With descriptions, the agent's schema context includes:
> `pe_ratio` — "Price-to-earnings ratio. Lower values may indicate undervaluation. Can be negative for loss-making companies."

This is a non-negotiable rule added to `CLAUDE.md`: **always add `Field(description=...)` to every field in every Pydantic model.**

---

## Phase 2 — Configuration

### Q: Why use `BaseSettings` over a plain settings class?
Three concrete advantages over a plain `class Settings`:

1. **Automatic env var reading** — no manual `os.getenv()` calls. If `APP_ENV` is set in the shell or `.env`, Pydantic maps it to the right field automatically, including type coercion (`PORT=8080` as a string becomes `int`).
2. **Type validation at startup** — if someone sets `PORT=abc`, the app crashes immediately at import time with a clear `ValidationError`, not silently at runtime. Same Pydantic guarantees used everywhere else, applied to config.
3. **Layered config priority** — `SettingsConfigDict` enforces: `shell env vars > .env file > field defaults`. In production you inject secrets via Docker/shell env vars and they automatically override `.env` — no code changes between environments.

Plain class comparison:
```python
# Plain — manual casting, ungraceful errors
class Settings:
    PORT = int(os.getenv("PORT", 8080))  # must cast manually

# BaseSettings — automatic, validated, environment-aware
class Settings(BaseSettings):
    PORT: int = 8080  # cast + validated automatically
```

---

### Q: What can `SettingsConfigDict` be used for beyond `.env` configuration?
It has several practical uses:

1. **`.env` file** (what we use now):
```python
SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
```

2. **Environment variable prefix** — avoids name collisions when multiple services share the same environment:
```python
SettingsConfigDict(env_prefix="STOCK_AGENT_")
# PORT in code maps to STOCK_AGENT_PORT in the environment
```

3. **Case sensitivity control** — by default env vars are case-insensitive; enforce strict casing if needed:
```python
SettingsConfigDict(case_sensitive=True)
```

4. **Secrets directory** (Docker/Kubernetes) — reads secrets from mounted files instead of env vars:
```python
SettingsConfigDict(secrets_dir="/run/secrets")
# Reads /run/secrets/DATABASE_URL as the DATABASE_URL value
```

5. **Extra fields behaviour**:
```python
SettingsConfigDict(extra="forbid")  # crash if unknown env vars are passed
SettingsConfigDict(extra="ignore")  # silently ignore unknown vars (default)
```

In this project we use `.env` config now. The secrets directory pattern becomes relevant in Phase 10 when Docker is introduced.

---

## Async & Threading Concepts

### Q: What is the risk of making blocking calls inside an async function, and how does `asyncio.to_thread()` solve it?

**The core problem — blocking the event loop:**

The event loop is **single-threaded**. When you write `async def`, you're telling Python this function runs on the event loop. The event loop can juggle many coroutines concurrently, but only by switching between them at `await` points. A blocking call inside `async def` has no `await` — it freezes the entire thread:

```python
# ❌ WRONG — looks async but secretly blocks everything
async def fetch_valuation_metrics(ticker: str):
    info = yf.Ticker(ticker).info  # blocking HTTP call, no await
    # During this 1-3 second call: no other coroutines run,
    # no UI updates, no other requests — the whole app stalls
```

**The fix — `asyncio.to_thread()`:**

`asyncio.to_thread()` offloads the blocking function to a **thread pool worker**, freeing the event loop to continue handling other work. When the thread finishes, the result is handed back to the event loop:

```python
# ✅ CORRECT — blocking work runs in a thread, event loop stays free
async def fetch_valuation_metrics(ticker: str):
    info = await asyncio.to_thread(_get_ticker_info, ticker)
    # Event loop is free during the network call
    # Other coroutines run normally while we wait
```

**Why this matters especially in this project:**

In Phase 9, Celery workers run `asyncio.run(_async_run_fundamental())` which fetches data for multiple tickers concurrently via `asyncio.gather()`. Without `asyncio.to_thread()`, the gather is fake — it runs sequentially. With it, all fetches run truly in parallel:

```python
# With asyncio.to_thread — truly concurrent, ~3 seconds total
await asyncio.gather(
    fetch_valuation_metrics("AAPL"),   # thread 1
    fetch_valuation_metrics("MSFT"),   # thread 2
    fetch_valuation_metrics("NVDA"),   # thread 3
)

# Without asyncio.to_thread — sequential, ~9 seconds total
# The gather still awaits each one, but each one blocks while running
```

**Rule of thumb for the async/sync boundary:**
> Any library that makes network I/O or disk I/O synchronously (yfinance, tvDatafeed, DuckDuckGo) must be wrapped with `asyncio.to_thread()` when called from inside an `async def`. Otherwise you have a fake async function that silently destroys concurrency.

This pattern appears throughout the project:
- `yf_client.py` — yfinance `.info` calls
- `core_data.py` (Step 14) — tvDatafeed `get_hist()` calls
- `web_search.py` (Step 9) — DuckDuckGo `DDGS().text()` calls

---

## Phase 3 — Technical Data Ingestion

### Q: How does OHLCV data cleaning work, and why is it critical before passing to indicator modules?

**The cleaning pipeline in `validate_ohlcv()`:**

**Step 1 — Column check:**
Verify all 5 required columns exist (`Open`, `High`, `Low`, `Close`, `Volume`). If any are missing the function raises `ValueError` immediately — there is no point continuing with incomplete data.

**Step 2 — `ffill().bfill()` — fill NaN values:**

Real market data has gaps. Exchanges are closed on weekends and holidays, data vendors occasionally miss sessions, and some tickers have thin trading history. These gaps show up as NaN in the DataFrame.

`ffill()` (forward fill) — carries the last known value forward:
```
Date        Close
Monday      100.0
Tuesday     NaN    → filled with 100.0  (Monday carried forward)
Wednesday   NaN    → filled with 100.0  (still carrying forward)
Thursday    102.0
```

`.bfill()` (backward fill, chained after ffill) — fills the next known value backward. Handles NaN at the very start of the DataFrame where ffill has nothing to carry forward:
```
Date        Close
Row 1       NaN    → ffill fails (no prior value), bfill fills with Row 2's value
Row 2       100.0
```

Together they guarantee **zero NaN values anywhere in the DataFrame** — ffill handles middle/end gaps, bfill handles start gaps.

**Step 3 — Minimum row count (200):**
Reject DataFrames with fewer than 200 rows. SMA_200 requires exactly 200 bars of history to produce a meaningful value — feeding it less would silently produce NaN or wrong results in downstream indicator modules.

**Why this matters — the chain of responsibility:**
The cleaned DataFrame returned by `fetch_ohlcv()` is the **single source of truth** for all technical work. Every indicator module (SMA, MACD, VCP, Trend Template) receives this same DataFrame and appends its computed columns to it, passing it forward like a chain:

```
fetch_ohlcv()
    → validate_ohlcv()       ← quality gate — clean or reject
        → add_moving_averages()   ← appends SMA_50, SMA_150, SMA_200
            → add_macd()          ← appends MACD columns
                → check_trend_template()  ← reads all appended columns
```

If NaN values were allowed through, they would silently corrupt every indicator computed downstream — wrong scores, wrong recommendations, wrong output to the user. The cleaning step is a non-negotiable contract: **every module in the chain can trust the DataFrame it receives is complete and well-formed.**

---

### Q: Why did we drop tvdatafeed and use yfinance for OHLCV instead?
`tvdatafeed` was the original plan for fetching OHLCV technical data from TradingView, but was dropped for production due to:

1. **Not on PyPI** — only installable from GitHub (`pip install git+https://...`), meaning no versioned releases, no stability guarantees
2. **Unmaintained** — syntax warnings in its own source code, no active development
3. **Unofficial scraper** — connects to TradingView's websocket without official API support; TradingView can break or block it at any time without notice

`yfinance` covers both fundamental AND technical data:
- Fundamental: `yf.Ticker(ticker).info` — P/E, revenue growth, market cap, peers
- Technical OHLCV: `yf.Ticker(ticker).history(period="2y")` — returns a clean DataFrame with `Open`, `High`, `Low`, `Close`, `Volume` columns that `pandas-ta` works with directly

**Rule of thumb for production dependencies:** if a library is not on PyPI, has no versioned releases, or relies on an unofficial/scraped API — find an alternative.

---

### Q: What about scraping TradingView charts with a vision model to read indicator values?
Evaluated and rejected. The approach would be: log in with a generic TradingView account → screenshot the chart with indicators → feed to a vision model to extract values.

Problems:
1. **Fragile** — TradingView can change their UI at any time, breaking the scraper silently
2. **Inaccurate** — vision models are terrible at extracting precise float values from chart pixels (e.g. `SMA_200 = 187.43`)
3. **Violates CLAUDE.md rule** — "NEVER allow the AI agent to compute or estimate any numerical indicator" — vision model reading chart values is exactly this
4. **Slow and costly** — screenshot + vision API call adds 3-5 seconds and token cost per analysis
5. **ToS violation** — scraping TradingView likely violates their terms of service

Vision models are useful for qualitative chart pattern recognition ("does this look like a cup and handle?") — never for extracting precise numerical values. `yfinance` + `pandas-ta` computes the same values deterministically in milliseconds for free.

---

## Phase 2 — Fundamental Pipeline

### Q: The user only provides a ticker symbol — how do we get the full company name for news searches?
yfinance provides the full company name via `info.get("longName")` (e.g. `"AAPL"` → `"Apple Inc."`). The solution is a small util function in `yf_client.py`:

```python
async def fetch_company_name(ticker: str) -> str:
    info = await asyncio.to_thread(_get_ticker_info, ticker)
    return info.get("longName") or ticker  # fallback to ticker symbol if not found
```

This will be added to `yf_client.py` before Step 26 (agent tool registration), where the tool flow will be:
```
user inputs "AAPL"
    → fetch_company_name("AAPL")             → "Apple Inc."
    → search_company_news("AAPL", "Apple Inc.")
    → search_recent_catalysts("AAPL", "Apple Inc.")
    → search_risk_news("AAPL", "Apple Inc.")
```

**Not implemented yet** — strictly out of scope until needed in Step 26. Follow the protocol, tell the story of progress in order.

---

### Q: How do we ensure the news search returns the most relevant and recent catalysts, not just generic price movement coverage?
This is critical to the application's value — returning generic "stock is up today" headlines is useless. The user needs to understand **why** the stock is moving and what recent events (earnings, dilution, lawsuits, product launches, macro events) are driving it.

**The problem with a generic query:**
```python
query = f"{ticker} {company_name} news"  # ❌ returns latest price movement articles, buries catalysts
```

**The solution — targeted multi-query strategy in Steps 10 & 11:**

Instead of one generic search, fire **multiple focused queries** and merge results:

**Catalyst queries (`search_recent_catalysts`):**
1. `"{ticker} {company_name} catalyst earnings revenue guidance {current_year}"`
2. `"{ticker} {company_name} shares offering dilution capital raise {current_year}"`
3. `"{ticker} {company_name} acquisition merger deal {current_year}"`
4. `"{ticker} {company_name} government contract partnership deal {current_year}"`
5. `"{ticker} {company_name} investor relations press release {current_year}"`

**Risk queries (`search_risk_news`):**
1. `"{ticker} {company_name} lawsuit SEC investigation {current_year}"`
2. `"{ticker} {company_name} fraud recall fine penalty {current_year}"`
3. `"{ticker} {company_name} bankruptcy debt risk warning {current_year}"`

Each query targets a specific category of event. Results are merged, deduplicated, and passed to the Ollama NLP sub-agent (Step 26) which extracts the most relevant snippets before the main agent reasons over them.

5. **Investor Relations (IR) website:**
   `"RKLB Rocket Lab investor relations press release {current_year} site:ir.rocketlabusa.com OR site:investors.rocketlabusa.com"`
   IR pages are the most authoritative source — they contain official press releases, earnings transcripts, capital raise announcements, forward guidance, and management commentary that may not yet be covered by financial media. This gives the agent direct access to what the company itself is saying about its future plans.

**Why deduplication matters — context engineering:**

When firing multiple overlapping queries, the same high-signal event (e.g. an earnings beat) will appear in several query results simultaneously because DuckDuckGo doesn't know our queries are related. Without deduplication:

```
["Q4 earnings beat...", "Q4 earnings beat...", "Q4 earnings beat...", "NASA contract signed..."]
```

With deduplication:
```
["Q4 earnings beat...", "NASA contract signed..."]
```

This is a **context engineering** concern — the LLM has a finite context window, and every token counts. Feeding duplicate snippets to the Ollama NLP sub-agent (Step 26) wastes context window tokens on redundant information, which:
1. Reduces the number of *unique* signals the agent can reason over
2. Artificially inflates the weight of repeated events in the agent's reasoning
3. Increases token cost with cloud models (OpenAI/Gemini) for no informational gain

The goal is to pass the **maximum number of unique, high-signal snippets** into the context window — not the maximum number of snippets. Quality over quantity is the core principle of context engineering.

**Key design decisions for Steps 10 & 11:**
- Always include `{current_year}` in queries — never hardcoded — to avoid stale results
- Use `max_results=5` per query rather than `max_results=10` on one query — better signal-to-noise ratio
- The `search_recent_catalysts` and `search_risk_news` functions (Step 10) must use specific query templates, not generic ones
- The `extract_risk_flags` function (Step 11) keyword-matches against the merged results to surface specific risk signals

**Bottom line:** the quality of the agent's final `StockReport` summary depends entirely on the quality of the news snippets fed into it. Targeted queries = better context = more valuable output for the user.

---

### Q: Is `extract_risk_flags()` a guardrails system? And since it's sync, does Celery call it directly?

**On risk flags as guardrails:**
`extract_risk_flags()` is a **signal filter**, not an AI safety guardrail. The distinction:
- `search_risk_news()` casts a wide net — returns anything DuckDuckGo finds for risk queries. Some snippets will be genuine red flags, others noise ("company has no known investigations")
- `extract_risk_flags()` narrows that down deterministically to only snippets containing concrete risk keywords

The LLM then reasons over pre-filtered, high-signal risk snippets rather than classifying noise itself. This is context engineering — deterministic filtering so the LLM focuses on reasoning, not classification.

**On sync functions and Celery:**
`extract_risk_flags()` is sync because it's pure computation — no I/O, just string matching. Calling a sync function inside an async context is always safe. The full call chain in Phase 9:

```
@celery.task def run_fundamental_task()        ← sync Celery task, no await
    → asyncio.run(_async_run_fundamental())    ← bridges sync → async
        → await search_risk_news()             ← async I/O (DuckDuckGo)
        → extract_risk_flags(snippets)         ← sync computation inside async — perfectly fine
```

It's only the reverse that causes problems: calling async from sync without a bridge (`asyncio.run()`).

---

### Q: When should we enforce Python rules vs. rely on LLM reasoning? How does this affect token cost and context quality?

**The core principle:** everything that can be decided deterministically should **never** reach the LLM. Only information that genuinely requires reasoning should consume context window tokens.

This is why `CLAUDE.md` enforces: *"ALL numerical calculations MUST be completed by the deterministic pipeline BEFORE any LLM is invoked."* It's not just about correctness — it's about cost efficiency and context quality too.

| Concern | Handle with Python (deterministic) | Pass to LLM (reasoning) |
|---|---|---|
| **News relevance** | `extract_risk_flags()` keyword-filters non-risk snippets | Only confirmed risk signal snippets |
| **Duplicate content** | `_deduplicate()` removes repeated snippets | Only unique news events |
| **Technical indicators** | pandas-ta computes SMA, MACD, VCP mathematically | Only the pre-computed values |
| **Scoring math** | `calculate_fundamental_score()` applies weights and clamps | Only the final score floats |
| **Peer list size** | `fetch_industry_peers()` caps at 10 tickers | Only the relevant peer subset |
| **Data validation** | `validate_ohlcv()` checks NaN, row count, required columns | Only a clean, validated DataFrame |
| **Weight validation** | `ScoringStrategy` validator ensures weights sum to 1.0 | Never — pure constraint enforcement |
| **Risk keyword matching** | `extract_risk_flags()` string-matches against `RISK_KEYWORDS` | Never — deterministic classification |
| **Final recommendation** | N/A — too nuanced for rules | LLM synthesises all signals into BUY/WATCH/AVOID |
| **Analyst narrative** | N/A — requires language and context | LLM writes the `summary` field |
| **Cross-signal reasoning** | N/A — requires holistic judgement | LLM connects fundamental + technical + news signals |

**The mental model:**
- If a 5-line Python function can do it reliably → do it in Python, never in the LLM
- If it requires synthesising multiple signals, understanding context, or producing language → that's what the LLM is for

Every deterministic filter applied before the LLM means:

---

### Q: How does the fundamental scoring algorithm work? What is the calculation formula?

The scorer receives a `FundamentalData` object and a `ScoringStrategy` and returns a single float in `[1.0, 10.0]`. Three concerns are computed in strict order:

**Step 1 — Sub-score per metric (0.0 → 1.0)**
Each active metric's raw value is normalised independently into a 0.0–1.0 sub-score based on financial logic:
- `pe_ratio`: lower is better — P/E of 15 scores ~0.80, P/E of 50 scores ~0.30, `None` scores 0.0
- `revenue_growth`: higher is better — 50% growth scores ~0.90, negative growth scores ~0.10
- `market_cap`: higher is better — larger cap = more stability
- `beta`: closer to 1.0 is neutral — very high beta (>2) penalised as excess risk

**Step 2 — Re-normalise weights of active metrics**
Only the metrics listed in `strategy.fundamental_metrics` are included. Their weights are fetched from `METRIC_WEIGHTS` in `config.py`, then re-normalised so they sum to 1.0:
```
active_weights = {m: METRIC_WEIGHTS[m] for m in strategy.fundamental_metrics}
total = sum(active_weights.values())
normalised = {m: w / total for m, w in active_weights.items()}
```
This ensures excluding a metric never artificially shrinks the score range.

**Step 3 — Weighted sum → scale → clamp**
```
weighted_sum = Σ (sub_score[m] × normalised_weight[m])   # 0.0 → 1.0
final_score  = 1.0 + weighted_sum × 9.0                  # scale to 1.0 → 10.0
final_score  = clamp(final_score, 1.0, 10.0)              # safety net
```

**Concrete example — strategy: `["pe_ratio", "revenue_growth"]`**

| Metric | Raw value | Sub-score | Base weight | Re-normalised weight | Contribution |
|---|---|---|---|---|---|
| `pe_ratio` | 15.0 | 0.80 | 0.4 | 0.5 | 0.40 |
| `revenue_growth` | 0.25 | 0.70 | 0.4 | 0.5 | 0.35 |
| **Total** | | | | | **0.75** |

`final_score = 1.0 + 0.75 × 9.0 = 7.75`

**Single metric example — strategy: `["pe_ratio"]` only**

| Metric | Raw value | Sub-score | Re-normalised weight | Contribution |
|---|---|---|---|---|
| `pe_ratio` | 15.0 | 0.80 | 1.0 | 0.80 |

`final_score = 1.0 + 0.80 × 9.0 = 8.2`

The weight being `1.0` means this metric alone determines the entire score — but the raw value `15` never flows through directly. It was already converted to sub-score `0.80` before weighting.

**Key rule:** sub-score and weight are always independent. Sub-score answers *"how good is this value?"*, weight answers *"how much do we care?"*

---

### Q: Where does the 50% weight come from? What do the `1` and `9` mean in the scaling formula?

**Where the 50% comes from — re-normalisation visualised:**

Each metric has a base weight in `METRIC_WEIGHTS`. When only a subset is active, their weights are re-scaled so they always sum to 1.0 (100%):

```
Strategy: ["pe_ratio", "revenue_growth"]

Base weights:
┌─────────────────┬──────────┐
│ pe_ratio        │  0.4     │
│ revenue_growth  │  0.4     │
│ market_cap      │  0.1     │  ← excluded, ignored
│ beta            │  0.1     │  ← excluded, ignored
└─────────────────┴──────────┘

Active total = 0.4 + 0.4 = 0.8

Re-normalised:
┌─────────────────┬──────────────────────────┐
│ pe_ratio        │  0.4 / 0.8 = 0.50 (50%)  │
│ revenue_growth  │  0.4 / 0.8 = 0.50 (50%)  │
└─────────────────┴──────────────────────────┘
                            total = 1.00 ✓
```

If the strategy were `["pe_ratio", "market_cap"]` instead:
```
Active total = 0.4 + 0.1 = 0.5

┌─────────────────┬──────────────────────────┐
│ pe_ratio        │  0.4 / 0.5 = 0.80 (80%)  │
│ market_cap      │  0.1 / 0.5 = 0.20 (20%)  │
└─────────────────┴──────────────────────────┘
                            total = 1.00 ✓
```

The weights always re-normalise to 1.0 regardless of which metrics are active.

---

**What do the `1` and `9` mean — range scaling visualised:**

Our weighted sum is always between `0.0` and `1.0`. We want the final score between `1.0` and `10.0`. The formula maps one range onto the other:

```
scaled = min_target + (value × (max_target - min_target))
       = 1.0        + (value × (10.0       - 1.0))
       = 1.0        + (value × 9.0)

  1.0  = the FLOOR  of our target range
  9.0  = the WIDTH  of our target range (10 - 1)
```

Visualised as a number line:

```
Weighted sum:   0.0 ──────────────── 0.5 ──────────────── 1.0
                 │                    │                     │
                 ▼                    ▼                     ▼
Final score:   1.0 ──────────────── 5.5 ──────────────── 10.0

Formula check:
  worst:   1.0 + (0.0 × 9.0) =  1.0  ✓
  average: 1.0 + (0.5 × 9.0) =  5.5  ✓
  best:    1.0 + (1.0 × 9.0) = 10.0  ✓
```

This formula works for any target range. Examples:
```
0–100:   0   + value × 100
1–5:     1.0 + value × 4.0
0–10:    0   + value × 10.0
```

The `1` ensures the **worst possible stock never scores zero** — a score of 1.0 means "very poor" not "no data". The `9` stretches the full width of the remaining range.

---

**Normalisation ranges used in Step 12:**
| Metric | Range | Logic |
|---|---|---|
| `pe_ratio` | `[0, 50]` — lower is better | P/E of 0–15 = cheap, 30 = fair, 50+ = expensive |
| `revenue_growth` | `[0, 1.5]` — higher is better | Capped at 150% to accommodate high-growth small caps (e.g. early NVDA, TSLA) |
| `market_cap` | `[0, 1T]` — higher is better | $1T+ = full score; smaller caps score proportionally lower |
| `beta` | sweet spot `~1.0` — penalise extremes | beta > 2.0 penalised as excess risk; beta < 0 also penalised |

---

### Future enhancement: add `scoring_profile` to `ScoringStrategy`
The normalisation ranges above are a compromise — they work for balanced/growth strategies but are not ideal for pure value investors. A future `scoring_profile` field should be added to `ScoringStrategy` to dynamically select ranges from a lookup table in `config.py`:

```python
# Future design
class ScoringStrategy(BaseModel):
    scoring_profile: Literal["value", "balanced", "growth"] = "balanced"
    # "value"   → pe_ratio max=20, revenue_growth max=0.15
    # "balanced"→ pe_ratio max=35, revenue_growth max=0.50
    # "growth"  → pe_ratio max=60, revenue_growth max=1.50
```

This allows the scorer to dynamically select normalisation ranges based on the investor's strategy type without changing the scorer interface. **Not implemented yet — implement when ScoringStrategy is extended in a future phase.**

Every deterministic filter applied before the LLM means:
1. **Fewer tokens** → lower cost per analysis
2. **Higher signal density** → better reasoning quality
3. **Consistent behaviour** → same input always produces same filtered output, regardless of model temperature

---

### Q: What happens when yfinance returns an empty industry peers list?
yfinance's `industryPeers` field is unreliable — it returns `[]` for many tickers (confirmed with IREN and TSM). This breaks the peer comparison feature entirely if left unhandled.

**Proposed countermeasure for Step 30 (`get_peer_reports`):**
Implement a fallback chain when `fetch_industry_peers()` returns `[]`:

1. **DuckDuckGo search fallback** — query `"{ticker} industry peers competitors similar stocks"` and parse ticker symbols from the results
2. **Screener fallback** — query a financial screener (e.g. Finviz, Macrotrends) via DuckDuckGo and extract peer tickers from the page

The fallback should be transparent — the agent tool always returns a peers list, the caller never needs to know which source was used. Cap the result at 10 tickers regardless of source.

This should be implemented in `fetch_industry_peers()` in `yf_client.py` as a layered fallback, keeping the screener/web logic in `web_search.py`.

---

### Q: Why is `_fetch_history` decorated with `@lru_cache`, and what does that mean?

`lru_cache` (Least Recently Used cache) memoizes a function's return value keyed by its arguments. The first call with a given ticker executes the function and stores the result in memory. Every subsequent call with the same argument returns the cached result instantly — no code runs again.

```python
_fetch_history("AAPL")  # hits yfinance HTTP → result stored in cache
_fetch_history("AAPL")  # returns cached DataFrame, zero network I/O
_fetch_history("MSFT")  # different arg → new HTTP call → stored separately
```

**Why `_fetch_history` specifically, and not `fetch_ohlcv`?**
Two reasons:
1. `_fetch_history` is the actual bottleneck — it is the one making the blocking HTTP call to yfinance. Caching it prevents redundant network round trips at the source.
2. `lru_cache` does not work on `async def` functions — it cannot intercept a coroutine's result. `_fetch_history` is a plain `def`, so the decorator works correctly on it.

**Is the cache per user or per server?**
Per server (process-level). `lru_cache` is an in-memory dictionary attached to the function object itself — there is no concept of "user" at this level. If User A fetches AAPL, User B requesting AAPL immediately after gets the cached result. The cache persists as long as the Python process is running. A process restart clears it entirely.

**The main scenario this solves in this project:**
During a peer analysis run, the same ticker can be requested multiple times — once as the primary subject, and again if it appears in another ticker's peer list. Without the cache, each request triggers an identical HTTP call. With the cache, only the first call hits the network.

---

### Q: What is `cachetools.TTLCache` and when would we use it instead of `lru_cache`?

`lru_cache` has one meaningful limitation for financial data: **it never expires**. If AAPL was fetched at 9am and a user requests it again at 3pm, they receive the 9am data — the cache has no concept of staleness.

`cachetools.TTLCache` solves this with a time-to-live (TTL) per entry:

```python
from cachetools import TTLCache, cached

# Cache up to 128 tickers; each entry expires after 15 minutes
_history_cache: TTLCache = TTLCache(maxsize=128, ttl=900)

@cached(cache=_history_cache)
def _fetch_history(ticker: str) -> pd.DataFrame:
    return yf.Ticker(ticker).history(period="2y")
```

After `ttl` seconds, the entry is evicted automatically. The next call fetches fresh data from yfinance and repopulates the cache.

**Why we use `lru_cache` now and not `TTLCache`:**
The current protocol scope uses `_fetch_history` primarily for deduplication within a single analysis run — not for long-session caching across many user requests. `lru_cache` is sufficient for that, requires no extra dependency, and keeps the implementation simple.

`TTLCache` becomes the right choice when:
- The server is long-lived and serves many users over hours
- Data freshness matters (intraday analysis, live dashboards)
- The cache needs to auto-refresh without a process restart

This would be the upgrade path for a production deployment.

---

## Phase 4 — Advanced Technical Analysis Logic

### Q: Where does `price_above_mas` get its SMA data from? Does it make a separate fetch?

No separate fetch. By the time `price_above_mas` runs, `add_moving_averages` (Step 17) has already appended `SMA_50`, `SMA_150`, and `SMA_200` as columns directly onto the same OHLCV DataFrame. The function simply reads the last row:

```
Date        Open    High    Low     Close   Volume    SMA_50   SMA_150   SMA_200
2025-03-18  69.10   70.20   68.50   69.48   ...       77.01    61.75     55.82
```

```python
Close[-1]   → df["Close"].iloc[-1]
SMA_150[-1] → df["SMA_150"].iloc[-1]
SMA_200[-1] → df["SMA_200"].iloc[-1]
```

This is the **Chain of Responsibility pattern** in practice — each module appends its computed columns to the DataFrame and returns it. Every subsequent function reads whatever columns it needs from the same enriched object. Nothing is fetched twice, no module needs to know where prior columns came from.

```
fetch_ohlcv()              → raw OHLCV (Open, High, Low, Close, Volume)
  → add_moving_averages()  → appends SMA_50, SMA_150, SMA_200
      → add_macd()         → appends MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
          → price_above_mas(), ma200_trending_up(), detect_vcp()  → read all of the above
```

---

### Q: What does `price_above_mas` check and why does it matter?

```python
def price_above_mas(df: pd.DataFrame) -> bool:
    return df["Close"].iloc[-1] > df["SMA_150"].iloc[-1] and \
           df["Close"].iloc[-1] > df["SMA_200"].iloc[-1]
```

It checks whether the current closing price is **strictly above both the 150-day and 200-day moving averages**. Both conditions must be true — equal does not count.

**Why these two MAs specifically:**
The 150 and 200-day SMAs represent medium and long-term institutional interest. A stock trading above both means institutions have been accumulating over 7–10 months — the trend is broadly upward. A stock below either is in distribution or recovery and is not a Minervini setup.

**Why strictly above (not >=):**
A stock sitting exactly on its 200-day SMA is at a critical support/resistance level, not in confirmed uptrend territory. The strict check enforces that the stock has broken clear of the MA, not just touched it.

This is one of five boolean checks that `check_trend_template` (Step 23) will aggregate into a single `True/False` verdict. Each check is its own function so they can be independently tested and composed cleanly.

---

### Q: What are the five Minervini Trend Template conditions and why does every one need to pass?

`check_trend_template` aggregates five boolean checks into a single `True/False` verdict. All five must be `True` — one failure disqualifies the stock immediately:

| Condition | Check | Why |
|---|---|---|
| 1. Price above MAs | `close > SMA_150 and close > SMA_200` | Stock is above medium and long-term institutional accumulation levels |
| 2. 200-day MA trending up | `SMA_200[-1] > SMA_200[-20]` | Long-term trend is genuinely rising, not just temporarily elevated |
| 3. 50-day above 150 and 200 | `SMA_50 > SMA_150 and SMA_50 > SMA_200` | Short-term trend is leading — MAs in correct bullish order |
| 4. Close > 75% of 52w high | `close > high_52w * 0.75` | Stock hasn't collapsed from its highs — still in the same trend |
| 5. Close > 130% of 52w low | `close > low_52w * 1.30` | Stock has already made a meaningful move — not still in base-building phase |

**Why all five must pass:**
Each condition filters a different failure mode. A stock can pass four conditions and still be broken — for example, it could be above all its MAs but have collapsed 40% from its 52-week high (condition 4 fails). The Trend Template is designed to be a strict pre-filter, not a scoring system. It produces a binary yes/no, not a grade.

---

### Q: What is the VCP (Volatility Contraction Pattern) and how does `detect_vcp` measure it?

A VCP is a consolidation pattern where a stock's price swings get progressively tighter over time — like a spring being compressed before a breakout. It signals that selling pressure is drying up and the stock is coiling for the next move.

**How `detect_vcp` works:**

It takes the last 60 trading days, splits them into equal windows (default 3 windows of 20 days each), and measures the price range (max Close − min Close) in each window:

```
Window 1 (days 1–20):   range = max - min  (e.g. $10)
Window 2 (days 21–40):  range = max - min  (e.g. $5)
Window 3 (days 41–60):  range = max - min  (e.g. $2)

Each window must be strictly narrower: $10 > $5 > $2 → True
```

If any window is wider than the previous one, the contraction is broken → `False`.

**Why VCP and Trend Template serve different purposes:**
- `check_trend_template` answers: *"is this stock in a healthy long-term uptrend?"* — a broad filter, hundreds of stocks can pass at once
- `detect_vcp` answers: *"is this stock coiling right now, ready to break out?"* — a timing filter, identifies which stocks on the watchlist are actionable today

Trend Template gives you the watchlist. VCP tells you which ones to act on.

**Live examples (as of March 2026):**

| Ticker | Trend Template | VCP | Interpretation |
|---|---|---|---|
| ONDS | True | True | Strong setup — uptrend + coiling |
| RKLB | False | True | VCP forming but hasn't reclaimed all MAs yet |
| EOSE | False | False | No trend, no base |

---

## Phase 5 — Agent Assembly & Tool Registration

### Q: Why does `get_moving_average_signal` exist as a separate tool when `get_technical_data` already returns MA values?

`get_technical_data` runs the full pipeline — fetch OHLCV, run all indicators, score, return `TechnicalData`. It's a heavy, one-time call.

`get_moving_average_signal` is a lightweight follow-up the LLM can choose to call mid-reasoning — for example, to verify *why* `trend_template_passed=False` before writing its summary:

```
1. Agent calls get_technical_data("ONDS")  → trend_template=False, score=4.0
2. Agent wants to understand: is the price just barely below SMA-50, or far away?
3. Agent calls get_moving_average_signal("ONDS")
   → price=$10.75, sma_50=$10.99  (only 2.2% below — near-miss, not breakdown)
4. Agent writes: "Near-miss on trend template — price is within 2% of SMA-50..."
```

Without this tool, the agent either trusts the boolean blindly or re-runs the full pipeline (expensive) to verify one number.

**The principle:** give the agent a toolbox, not a single function. Let it decide how deep to go. Heavy tools give scored structure; lightweight tools give targeted follow-up without re-running the pipeline.

---

### Q: How does PydanticAI tool registration work? What does `@agent.tool` actually do?

`@agent.tool` is a decorator that registers a function on the agent at decoration time (import time). It does three things:

1. **Inspects the function signature** — builds a JSON schema from the parameters. This schema is sent to the LLM so it knows what arguments to pass.
2. **Registers the tool on the agent** — adds it to the agent's internal toolset.
3. **Wires up dependency injection** — any parameter typed as `RunContext[AgentDependencies]` is automatically populated by the framework at call time. The LLM never sees it.

```python
@agent.tool
async def get_technical_data(ctx: RunContext[AgentDependencies], ticker: str) -> TechnicalData:
    #                         ^^^^ injected by framework    ^^^^ LLM provides this
```

The LLM sees the tool as: `get_technical_data(ticker: string)`. `ctx` is invisible to it.

---

### Q: Why are tool modules imported at the bottom of `agent.py` instead of the top?

To avoid a circular import. The chain is:

- `fundamental_tools.py` imports `agent` from `agent.py` (to register tools on it)
- If `agent.py` also imported `fundamental_tools.py` at the top, Python would hit the import of `fundamental_tools` before `agent` was defined — and `fundamental_tools` would fail trying to import `agent` which doesn't exist yet

By placing the imports at the **bottom** of `agent.py`, after `agent = Agent(...)`, the object exists in memory before the tool files try to reference it:

```python
# agent.py
agent = Agent(...)   # defined here

# Tool modules imported here — triggers @agent.tool registration.
# Placed at the bottom to avoid circular imports.
import stock_agent.tools.fundamental_tools  # noqa: F401, E402
import stock_agent.tools.technical_tools
```

This is a standard Python pattern for circular dependency resolution via deferred imports.

---

### Q: Why is the Ollama sub-agent lazy-initialised with `@lru_cache` instead of at module level?

Two reasons:

1. **Offline resilience** — if Ollama is not running when the server starts, the module still imports cleanly. The Ollama agent is only constructed when a tool actually calls it.
2. **Singleton reuse** — `@lru_cache(maxsize=1)` ensures only one `Agent` instance is ever created. Without it, every `summarize_news_and_extract_risks` call would create a new `Agent` object.

```python
@lru_cache(maxsize=1)
def get_ollama_agent() -> Agent:
    # Only called on first tool invocation — not at import time
    return Agent(OpenAIModel("llama3.2", provider=OpenAIProvider(...)), output_type=NewsSummary)
```

Contrast with module-level instantiation:
```python
# ❌ Wrong — crashes at import time if Ollama is offline
ollama_agent = Agent(OllamaModel("llama3.2"), ...)
```

---

### Q: Why does pydantic-ai connect to Ollama via `OpenAIProvider` instead of a dedicated `OllamaModel`?

pydantic-ai v1.x has no dedicated Ollama module. Ollama exposes an **OpenAI-compatible REST API** at `/v1/chat/completions` — so pydantic-ai connects to it using the standard `OpenAIModel` pointed at the Ollama base URL:

```python
OpenAIModel(
    "llama3.2",
    provider=OpenAIProvider(
        base_url=f"{settings.OLLAMA_HOST}/v1",
        api_key="ollama",  # required placeholder — Ollama ignores auth
    ),
)
```

This works because Ollama implements the same API contract as OpenAI. The `api_key="ollama"` is a non-empty placeholder — the provider requires a value but Ollama does not enforce authentication.

---

### Q: How do you test a PydanticAI agent without a real API key or network calls?

Use `TestModel` from `pydantic_ai.models.test`. It never makes HTTP calls — it generates a structured output directly from the `output_type` schema:

```python
from pydantic_ai.models.test import TestModel

with agent.override(model=TestModel(call_tools=[], custom_output_args={...})):
    result = await agent.run("Analyse AAPL", deps=deps)
    assert isinstance(result.output, StockReport)
```

Key parameters:
- `call_tools=[]` — skip tool invocations entirely; go straight to producing output
- `call_tools='all'` — invoke all registered tools (default) — requires real data sources to be available
- `custom_output_args` — provide a valid dict matching the `output_type` schema; needed when fields like `datetime` fail TestModel's default single-character dummy values

For **direct tool testing**, bypass the agent entirely — call the tool function with a `MagicMock` ctx:
```python
from unittest.mock import MagicMock

ctx = MagicMock()
ctx.deps = AgentDependencies(strategy=ScoringStrategy())
result = await get_technical_data(ctx, "AAPL")  # real yfinance call, no agent overhead
```

---

### Q: What should the frontend display when `pe_ratio` is None?
`pe_ratio` returns `None` from yfinance when the company has no earnings (i.e. not yet profitable — e.g. early-stage biotech, high-growth pre-profit tech). This has a specific financial meaning and must be communicated clearly to the user.

Display rules for `report_card.py` (Step 34):
- `pe_ratio = None` → `"N/A — company not yet profitable"`
- `revenue_growth = None` → `"N/A — data unavailable"`
- `beta = None` → `"N/A — data unavailable"`
- `market_cap = None` → `"N/A — data unavailable"`

`pe_ratio` gets a specific explanation because `None` has a clear financial meaning. The others are more likely just missing data from yfinance and should show a generic unavailable message.

---

## Phase 5 — CLI & Entry Point

### Q: Why is `main.py` inside `src/stock_agent/` instead of the project root?

Four reasons:

1. **`-m` flag requires a package module** — `uv run python -m stock_agent.main` only works if `main.py` is inside the `stock_agent` package. A root-level `main.py` can't be addressed with `-m` this way.

2. **`src/` layout convention** — this project follows the standard `src/` layout (used by `hatchling`/`uv`). All application code lives under `src/`; the root is reserved for project config files (`pyproject.toml`, `docker-compose.yml`, `.env`, etc.).

3. **Import consistency** — `main.py` imports from `stock_agent.agent`, `stock_agent.models`, etc. Living inside the package means those imports resolve cleanly without any `sys.path` hacks.

4. **Installable entry point** — placing it in the package allows `pyproject.toml` to expose it as a proper CLI entry point:
   ```toml
   [project.scripts]
   stock-agent = "stock_agent.main:main"
   ```
   This is how tools like `uvicorn`, `celery`, and `pytest` work — they're all package entry points, not root scripts.

A root-level `main.py` is a quick-script pattern suitable for small one-file projects. For a structured package with workers, a UI, and a DB layer, it belongs inside the package.

---

### Q: Is there a size limit on CLAUDE.md? When should it be split?

There is no hard enforced limit on `CLAUDE.md`. The 200-line limit Eran flagged applies specifically to `MEMORY.md` (the memory index file loaded into every conversation). `CLAUDE.md` is loaded as project instructions and has no equivalent truncation threshold.

That said, the practical guideline is **~250 lines** — beyond that, the file becomes harder to scan and maintain. Current size: ~175 lines.

**If it grows past ~250 lines**, split verbose sections into separate files under `.claude/` and reference them with `@` imports:
```
@.claude/rules.md
@.claude/architecture.md
```
The commit protocol already uses this pattern (`@.claude/commit-protocol.md`).

*Raised by Eran during Step 28 — noted as a maintenance concern to keep an eye on as new rules are added.*

---

## Phase 8 — Database Layer

### Q: Why is `db.refresh()` called after every commit in the CRUD layer?

After `db.add()` + `await db.commit()`, PostgreSQL has the complete row including all server-generated values (`created_at`, `updated_at`). The in-memory Python object is still in the state it was constructed — timestamp fields are `None`.

`await db.refresh(obj)` fires a `SELECT` on that specific row and re-populates the Python object with whatever PostgreSQL actually stored. It acts as a **pull from DB → sync to memory** — after `refresh()`, the Python object is a true mirror of the DB row, including timestamps.

```python
db.add(job)              # Python: job_id=✓, created_at=None
await db.commit()        # Postgres: job_id=✓, created_at=2026-03-24 11:32:00
await db.refresh(job)    # Python: job_id=✓, created_at=2026-03-24 11:32:00 ✓
```

The session uses `expire_on_commit=False` to prevent lazy-load crashes, but that does not populate server-generated values — `refresh()` is still required for that. Without it, callers would receive an object with `None` timestamps.

*Raised by Eran during Step 42 review.*

---

### Q: Why do we have a dedicated CRUD layer instead of writing DB calls inline?

Three reasons: **separation of concerns**, **session ownership**, and **testability**.

**Separation of concerns:** FastAPI route handlers, Celery tasks, and the NiceGUI layer all need to read and write data, but none of them should know *how* data is stored. If we ever change the schema, add caching, or switch a query strategy, we change it in one place — `crud.py` — and every caller gets the fix automatically. Writing `session.execute(select(...))` directly in a route handler couples the HTTP layer to the storage implementation.

**Session ownership:** The CRUD functions accept an injected `AsyncSession` — they never create one themselves. This means the *caller* controls the transaction boundary. A FastAPI route can wrap multiple CRUD calls in a single session (one DB connection for the whole request). A Celery task does the same. If CRUD functions created their own sessions internally, each call would open and close its own connection — wasteful, and impossible to group into a single transaction.

**Testability:** Because CRUD functions are pure async functions that take a session and return data, they can be tested in complete isolation with an in-memory SQLite session — no HTTP server, no Celery worker, no live Postgres required. Testing a route handler that has DB calls baked in requires spinning up the full stack.

```
FastAPI route  ─┐
Celery task    ─┼─→  crud.py  →  AsyncSession  →  PostgreSQL
NiceGUI panel  ─┘
```

Each caller passes in its own session. `crud.py` is the only layer that knows SQL.

*Raised during Step 42 documentation review.* in both `report_json` and dedicated columns?

`StockReportRecord` stores two representations of the same report:

1. **`report_json`** — the full `StockReport` serialised via `model_dump(mode="json")`. Source of truth, nothing is lost.
2. **`fundamental_score`, `technical_score`, `weighted_score`, `recommendation`** — typed columns copied from the report at insert time.

The dedicated columns exist so the API and UI can query, sort, and filter by score without deserialising the JSON blob on every row. A `WHERE weighted_score > 7.0` query hits an indexed `Numeric(4,1)` column directly — fast and type-safe. Parsing `report_json` for the same value would require a JSON extraction expression on every row.

This is a standard **denormalization** pattern: accept a small amount of data duplication at write time in exchange for significantly faster and simpler reads.

*Raised by Eran during Step 42 review.*

---

### Q: Why does `save_report` convert scores via `Decimal(str(round(score, 1)))` — why go through `str()`?

The score fields on `StockReport` are Python `float` values. PostgreSQL stores them as `Numeric(4, 1)` — exact decimals. The conversion bridge is:

```python
Decimal(str(round(score, 1)))
```

**Why not `Decimal(score)` directly?**
`Decimal(7.1)` inherits the float's binary representation — it gives you `Decimal('7.09999999999999964472863211994990706443786621093750')`. The imprecision is already baked in before PostgreSQL ever sees the value.

**Why `str()` first?**
`Decimal("7.1")` — constructed from a string — parses the human-readable representation exactly. `"7.1"` means 7.1, with no binary fraction approximation involved. The result is `Decimal('7.1')` — clean, exact, and what `Numeric(4, 1)` expects.

**Why `round(..., 1)` before that?**
`round(score, 1)` enforces the one-decimal-place contract before conversion. A score of `7.149999...` (float arithmetic artifact) becomes `7.1` before it ever touches `str()` or `Decimal`. Without it, edge cases in float arithmetic could produce values that violate the `Numeric(4, 1)` scale.

**Full chain:**
```python
score = 7.1          # Python float from pipeline
round(score, 1)      # → 7.1  (enforce 1 decimal place)
str(7.1)             # → "7.1" (human-readable, no binary drift)
Decimal("7.1")       # → Decimal('7.1') (exact, safe for Numeric(4,1))
```

This is the standard pattern for float → Decimal conversion in any financial or precision-sensitive context. See DEC-023.

*Raised by Eran during Step 42 documentation review.*

---

### Q: What is `aiosqlite` and why does it eliminate the need for Docker in DB tests?

**The problem without it:** Our production code uses `AsyncSession` with `asyncpg` (the async Postgres driver). Tests that exercise CRUD functions need a real database to talk to. Without `aiosqlite`, the only option is a live PostgreSQL instance — which means `docker-compose up`, waiting for the container to be healthy, and tearing it down after. This makes the test suite slow, fragile, and impossible to run without Docker installed.

**What `aiosqlite` provides:** `aiosqlite` is an async driver for SQLite — the same interface as `asyncpg`, but backed by SQLite instead of PostgreSQL. SQLite runs entirely in-process (no server, no network, no Docker), and the `sqlite:///:memory:` URL creates a database that exists only in RAM for the lifetime of the test.

**Why it works with our code unchanged:** SQLAlchemy's `AsyncSession` is database-agnostic. It doesn't care whether the engine underneath is `asyncpg` (Postgres) or `aiosqlite` (SQLite). The CRUD functions receive an `AsyncSession` and call `session.add()`, `session.execute()`, `db.refresh()` — none of that changes between environments. Swapping the driver is a one-line change in the test fixture:

```python
# Production (api.py / Celery task)
engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/stockagent")

# Tests (conftest.py) — same AsyncSession, different engine
engine = create_async_engine("sqlite+aiosqlite:///:memory:")
```

**The development benefit:** Running `uv run pytest tests/test_db.py` requires zero infrastructure — no Docker, no running Postgres, no environment variables. The in-memory SQLite DB is created fresh for every test, populated with exactly the rows the test inserts, and discarded when the test ends. Tests are fast, isolated, and portable across any machine.

**The trade-off:** SQLite and PostgreSQL are not identical. `Numeric(4,1)` precision, `DateTime(timezone=True)`, and `UNIQUE` constraints all behave slightly differently. For structural and CRUD unit tests this is fine — the differences don't affect the logic being tested. For migration testing and type-precision verification, a real Postgres instance (Tier 2 testing) is still needed.

*Raised by Eran during Step 42 documentation review.*
