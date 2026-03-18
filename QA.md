# Project Q&A Log

Running record of design and concept questions discussed during development.

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

### Q: What should the frontend display when `pe_ratio` is None?
`pe_ratio` returns `None` from yfinance when the company has no earnings (i.e. not yet profitable — e.g. early-stage biotech, high-growth pre-profit tech). This has a specific financial meaning and must be communicated clearly to the user.

Display rules for `report_card.py` (Step 34):
- `pe_ratio = None` → `"N/A — company not yet profitable"`
- `revenue_growth = None` → `"N/A — data unavailable"`
- `beta = None` → `"N/A — data unavailable"`
- `market_cap = None` → `"N/A — data unavailable"`

`pe_ratio` gets a specific explanation because `None` has a clear financial meaning. The others are more likely just missing data from yfinance and should show a generic unavailable message.
