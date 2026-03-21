# Engineering Decisions Log

A curated record of non-obvious design decisions made during the build of this project.
Each entry captures what was decided, who raised it, the options considered, and the reasoning behind the choice.

This log is evidence of genuine human-AI collaboration — Eran (engineer) and Claude (AI assistant) working through real tradeoffs together, not just generating code.

---

## DEC-001 — Drop tvDatafeed, use yfinance for all OHLCV data
**Raised by:** Claude during Phase 3 setup
**Context:** The original protocol specified `tvDatafeed` for technical OHLCV data. During dependency installation it became clear the library is unmaintained, has open compatibility issues with newer Python versions, and requires TradingView credentials.
**Options considered:**
- Keep tvDatafeed — familiar to traders but unmaintained, fragile
- Switch to yfinance for OHLCV — already used for fundamentals, actively maintained, no auth required
**Decision:** Switch entirely to yfinance. Eliminates a second data source dependency, simplifies authentication, and keeps the OHLCV pipeline consistent with the fundamentals pipeline.
**Outcome:** Protocol updated across `commit-protocol.md`, `CLAUDE.md`, and `config.py` to reflect yfinance as the single data source.

---

## DEC-002 — Hybrid model routing: Ollama for NLP, cloud model for final reasoning
**Raised by:** Eran in project architecture
**Context:** News summarisation and risk flag extraction need to run on potentially dozens of articles per analysis. Running this through a cloud model (OpenAI/Gemini) would be slow and expensive at scale.
**Options considered:**
- Cloud model for everything — simple, but costly and slow for high-volume NLP
- Local Ollama (`llama3.2`) for everything — cheap, but small models produce lower-quality structured reasoning
- Hybrid: Ollama for NLP extraction, cloud model for final `StockReport` generation
**Decision:** Hybrid routing. Ollama handles the high-volume, low-complexity tasks (summarise articles, extract risk keywords). The cloud model only sees the structured `NewsSummary` output — never raw article text — and focuses exclusively on final reasoning.
**Outcome:** Token costs reduced significantly. Cloud model context window stays lean and signal-rich.

---

## DEC-003 — Add `Field(description=...)` to every Pydantic model field
**Raised by:** Eran during model review
**Context:** Pydantic field descriptions are serialised into the agent's JSON schema, which is sent to the LLM as part of its tool context. Fields without descriptions give the LLM no semantic guidance.
**Options considered:**
- Skip descriptions — less verbose, faster to write
- Add descriptions to all fields — more code, but LLM reasoning quality improves directly
**Decision:** Mandatory descriptions on every field, enforced as a non-negotiable rule in `CLAUDE.md`. The LLM uses field names and descriptions to understand what data it is working with — a missing description is a missing signal.
**Outcome:** Rule added: `ALWAYS add Field(description=...) to every field in every Pydantic model`.

---

## DEC-004 — `@lru_cache` on `_get_ticker_info` to eliminate redundant yfinance HTTP calls
**Raised by:** Claude during Phase 2 implementation
**Context:** `fetch_valuation_metrics`, `fetch_earnings_growth`, `fetch_industry_peers`, and `fetch_company_name` all call `yf.Ticker(ticker).info`. Without caching, each function triggers a separate HTTP round trip to Yahoo Finance for the same ticker.
**Options considered:**
- No cache — simple, but 4 redundant HTTP calls per analysis
- Pass the `info` dict as a parameter — avoids redundant calls but pollutes every function signature
- `@lru_cache` on the sync helper `_get_ticker_info` — transparent to all callers, single cache
**Decision:** `@lru_cache(maxsize=128)` on `_get_ticker_info`. All callers share one cached response per ticker within a process lifetime, with no interface changes.
**Outcome:** Single HTTP call per ticker regardless of how many fundamental functions are called.

---

## DEC-005 — DuckDuckGo fallback for company name resolution
**Raised by:** Claude during Step testing (live ONDS run)
**Context:** yfinance's `longName` field is missing for some tickers. Without a company name, the news search queries (e.g. `"Ondas Holdings recent catalysts"`) degrade to raw ticker queries, producing low-quality or irrelevant results.
**Options considered:**
- Fall back to the ticker symbol — simple but produces bad search queries
- DuckDuckGo search for `"{ticker} stock"` — one additional search, returns a title with the company name
**Decision:** DuckDuckGo fallback in `fetch_company_name`. Strips the parenthetical ticker suffix from the result title (e.g. `"Ondas Holdings Inc. (ONDS) Stock Price..."` → `"Ondas Holdings Inc."`). Falls back to the raw ticker only if both sources fail.
**Outcome:** News search quality preserved for tickers with missing yfinance metadata.

---

## DEC-006 — Lazy import inside `get_peer_reports` to resolve circular dependency
**Raised by:** Claude during Step 30 implementation
**Context:** `agent.py` imports `fundamental_tools.py` at the bottom (to trigger `@agent.tool` registration). `fundamental_tools.py` imports `agent` at the top (to access the agent object). `run_analysis` is defined in `agent.py` *after* the tool imports — so a top-level import of `run_analysis` in `fundamental_tools.py` would fail at module load time.
**Options considered:**
- Move `run_analysis` above the tool imports in `agent.py` — breaks tool registration order
- Extract `run_analysis` into a third module — adds indirection, splits cohesion
- Lazy import inside the function body — defers import to call time, by which point both modules are fully loaded
**Decision:** Lazy import inside `get_peer_reports`. Standard Python pattern for circular imports. Documented in `GLOSSARY.md` under *Lazy Initialisation / Lazy Import*.
**Outcome:** Clean module load, no circular import error, no architectural change required.

---

## DEC-007 — Move FastAPI app from `agent.py` to dedicated `api.py`
**Raised by:** Eran during Step 29 review
**Context:** The protocol specified `agent.py` as the target file for the FastAPI app. Eran challenged this — `agent.py` is already responsible for the PydanticAI agent definition and `run_analysis`. Adding HTTP concerns to the same file would mix two distinct responsibilities.
**Options considered:**
- Keep FastAPI in `agent.py` — matches protocol, avoids a new file
- Move to `main.py` — wrong fit, `main.py` is the CLI entry point
- Dedicated `api.py` — clean separation, single responsibility per module
**Decision:** Dedicated `api.py`. Every HTTP concern in the project (FastAPI app, lifespan hook, request models, route handlers) lives exclusively in `api.py`. Protocol target file updated in commit message to reflect the change.
**Outcome:** Three clean modules with no overlapping responsibilities: `agent.py` (agent + analysis logic), `api.py` (HTTP layer), `main.py` (CLI).

---

## DEC-008 — Defer peer discovery fix, do not block Phase 5 completion (TASK-003)
**Raised by:** Eran during Step 30 testing
**Context:** yfinance's `industryPeers` field has been silently removed from the API — `fetch_industry_peers` always returns `[]`. The `get_peer_reports` tool is architecturally correct but non-functional.
**Options considered:**
- DuckDuckGo peer search — dynamic, but fragile ticker parsing
- Static industry lookup table in `config.py` — reliable, manual maintenance burden
- Third-party financial API — best coverage, adds a new dependency
- Defer and return empty list — unblocks Phase 5, strategy discussion deferred
**Decision:** Defer. The Step 30 logic is sound and handles `[]` gracefully. Blocking Phase 5 over a data provider gap is not warranted — logged as TASK-003 for a focused strategy discussion after Phase 5 completes.
**Outcome:** Phase 5 completed on schedule. TASK-003 in backlog with all options documented.

---

## DEC-009 — Mount NiceGUI onto FastAPI instead of running a separate server
**Raised by:** Eran during Step 31 review
**Context:** NiceGUI has its own built-in server (`ui.run()`). Running it standalone would mean two separate processes on two separate ports — one for the REST API, one for the UI.
**Options considered:**
- Standalone NiceGUI server — simple to start, but splits API and UI across two ports; requires CORS configuration and a reverse proxy in production
- Mount NiceGUI onto FastAPI via `ui.run_with(app)` — single process, single port, shared lifespan
**Decision:** Mount onto FastAPI. One server handles both REST API requests and browser UI requests. The `lifespan` hook initialises shared resources (DB pool, Redis) once for both. Deployment is simpler — one Docker container, one port to expose.
**Outcome:** `ui/app.py` calls `ui.run_with(app)` then `uvicorn.run(app, port=settings.PORT)`. `ui.run_with()` mounts NiceGUI as middleware on the FastAPI app — it does not accept a `port` argument. Port is owned by uvicorn, not NiceGUI. Discovered during Step 32 testing.

---

## DEC-010 — Enforce markdown update rules via Claude Code hooks rather than CLAUDE.md alone
**Raised by:** Eran after noticing the ARCHITECTURE.md update was missed following Step 31
**Context:** CLAUDE.md already contained a rule requiring proactive markdown updates. Despite this, the rule was missed after Step 31. A rule that requires judgment can be overlooked; a hook that fires at commit time cannot.
**Options considered:**
- Strengthen the CLAUDE.md rule with a more explicit checklist — passive, still relies on Claude not missing it
- Add a PreToolUse hook on `git commit` — active, fires at exactly the right moment, injects a checklist Claude must address
- Both together — belt and braces
**Decision:** Both. CLAUDE.md retains the rule (tells Claude *what* to do and *why*). A PreToolUse hook fires before every `git commit` and injects a 6-item checklist (ARCHITECTURE.md, DECISIONS.md, GLOSSARY.md, QA.md, MCP_SERVER.md, LEARNING_MATERIAL.md). A PostToolUse hook fires after every commit and instructs Claude to explain the next step automatically.
**Outcome:** `.claude/hooks/pre_commit_check.py` and `post_commit_next_step.py` added. Configured in `.claude/settings.json`. LEARNING_MATERIAL.md updated with a hooks concept entry.

---

## DEC-011 — UI calls POST /analyze via HTTP rather than importing run_analysis() directly
**Raised by:** Claude during Step 33 implementation
**Context:** The NiceGUI Analyse button needs to trigger a stock analysis. Two options: call `run_analysis()` directly from the UI code, or call `POST /analyze` via `httpx`.
**Options considered:**
- Import and call `run_analysis()` directly — simpler, no HTTP overhead, but tightly couples UI to the agent module
- Call `POST /analyze` via `httpx.AsyncClient` — one extra network hop locally, but the correct architecture for Phase 9
**Decision:** Call `POST /analyze` via HTTP. When Phase 9 introduces Celery, the endpoint will return a `job_id` instead of a `StockReport` — the UI handler only needs to change what it does with the response, not how it triggers the analysis. Coupling the UI to the HTTP contract now makes Phase 9 a drop-in change.
**Outcome:** `on_analyse()` in `app.py` uses `httpx.AsyncClient` to call the local API. Runs as an async coroutine so the NiceGUI event loop stays responsive during the 10-30s analysis.

---

## DEC-012 — Centralised theme module with semantic colour constants
**Raised by:** Claude during Step 37 implementation
**Context:** Colour values (Tailwind class fragments) were being hardcoded individually in each component. When a colour needs to change, hunting through multiple files is error-prone.
**Options considered:**
- Inline colours per component — simple but fragile; a colour change requires touching every file
- Central `theme.py` with a semantic `COLOURS` dict and `RECOMMENDATION_BADGE` mapping — single source of truth, one file to update
**Decision:** Central `theme.py`. `COLOURS` maps semantic roles (primary, success, muted, etc.) to Tailwind fragments. `RECOMMENDATION_BADGE` defines the badge classes canonical to the recommendation enum. `apply_theme()` enables dark mode per NiceGUI session. Components import from `theme.py` in future refactors.
**Outcome:** `src/stock_agent/ui/theme.py` created. `app.py` imports and calls `apply_theme()` on every page load. Subsequently expanded (TASK-004 context) to a full six-dict token system: `COLOURS`, `TYPOGRAPHY`, `SPACING`, `RADIUS`, `SHADOW`, `TRANSITIONS` — matching the token spec in the ui-designer agent.

