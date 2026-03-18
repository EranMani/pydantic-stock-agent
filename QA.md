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

## Phase 2 — Fundamental Pipeline

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
