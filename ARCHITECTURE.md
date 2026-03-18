# Architecture & Data Flow Diagrams

A living document describing the data flows and component interactions of the Autonomous PydanticAI Stock Analyst Agent.
Updated as each phase is built. All diagrams use [Mermaid](https://mermaid.js.org/) and render natively on GitHub.

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

*More diagrams will be added as phases are built.*
