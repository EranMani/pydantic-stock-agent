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
