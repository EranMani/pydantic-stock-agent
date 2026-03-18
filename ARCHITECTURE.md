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

*More diagrams will be added as phases are built.*
