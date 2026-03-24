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

---

## DEC-013 — Specialised sub-agent architecture for domain ownership
**Raised by:** Eran, as the codebase grows in complexity
**Context:** As the project scales, a single general-purpose Claude session handles everything — backend logic, UI work, database design, infrastructure — with no clear ownership boundary. Mistakes are more likely when one agent context-switches between domains without deep specialisation.
**Options considered:**
- Single agent (current default) — simpler, no delegation overhead, but shallow domain expertise and no accountability per area
- Specialised sub-agents per domain — each agent has a deep identity, hard boundaries, its own standards, and a persistent work log; the main session delegates and coordinates
**Decision:** Specialised sub-agents. Starting with `@ui-designer` (owns all NiceGUI/Tailwind frontend work). Future agents planned for backend database work and potentially infrastructure/DevOps. Each agent gets three files: an identity file (`ui-designer.md`), a skill file (`SKILL.md` with execution process per task type), and a live work log (`ui-designer-worklog.md`).
**Outcome:** `.claude/agents/ui-designer.md`, `.claude/skills/ui-designer/SKILL.md`, and `.claude/agents/logs/ui-designer-worklog.md` added. `CLAUDE.md` Section 6 routes UI/UX work to `@ui-designer`.

---

## DEC-014 — Control panel layout replacing stacked card form (Aria, approved by Eran)
**Raised by:** Eran — original dashboard felt dull, too vertical, no hierarchy
**Context:** The Phase 7 dashboard stacked every section in equal-weight cards. The Analyse button was buried at position four. The page read as a form, not a tool.
**Options considered:**
- Two-column layout (ticker/action left, strategy config right)
- Stacked with brutal hierarchy (accordion for strategy, hero ticker)
- Control panel — single horizontal control bar + collapsible strategy config (Aria's recommendation)
**Decision:** Control panel layout (Option C). Ticker input, weight slider, and Analyse button live in one card. Strategy config (pill toggles for metrics) collapses inside the same card via `ui.expansion()`. Page widened to `max-w-2xl` with proper card surfaces giving dark `gray-800` backgrounds.
**Outcome:** `app.py` and `strategy_panel.py` restructured. Checkboxes replaced with pill toggle buttons. `PILL_ACTIVE` / `PILL_INACTIVE` tokens added to `theme.py`.

---

## DEC-015 — `color=None` on NiceGUI buttons to allow Tailwind class control (Aria)
**Raised by:** Aria during pill toggle debugging
**Context:** `ui.button()` defaults to `color='primary'` which causes Quasar's scoped CSS to take specificity precedence over Tailwind `bg-*` classes. Visual state changes via `.classes()` were invisible — Quasar was winning the CSS war every time.
**Decision:** Always set `color=None` on any `ui.button()` where Tailwind classes control the visual appearance. This removes Quasar's color prop entirely and makes Tailwind the sole authority.
**Outcome:** Applied to all pill toggle buttons and the Analyse button. Pattern to follow for any future button with custom Tailwind styling.

---

## DEC-016 — Fixed full-bleed toolbar with height contract (Aria)
**Raised by:** Eran — page felt unmodern, title was floating with no visual anchor
**Context:** The "Stock Agent" title and subtitle were bare labels inside the content column — no background, no frame, no hierarchy. The page had no architectural top edge.
**Decision:** Full-bleed fixed toolbar, `gray-900` background, `h-14` (56px), with a 1px `indigo-600` bottom border accent. Brand name left, live status dot right. Inner content constrained to `max-w-2xl` to align with the body column. Body content column carries `pt-14` offset to clear the fixed header. Height contract: `h-14` and `pt-14` are coupled — both must change together if the header height ever changes.
**Outcome:** `app_header()` function added to `app.py`. `HEADER` token dict added to `theme.py` centralizing all header constants. Header background deliberately `gray-900` (not indigo) to avoid competing with the `indigo-600` primary action color.

---

## DEC-017 — Enforce score rounding at the Pydantic model level via a `Score` type alias
**Raised by:** Eran — score fields were returning floats with many decimal places
**Context:** The scoring pipeline produces raw floats (e.g. `7.134285714...`). These values flow into `FundamentalData`, `TechnicalData`, `PeerReport`, and `StockReport`. The question was where to enforce the 1-decimal rounding.
**Options considered:**
- Round in the display layer (report card, MCP tool formatters) — each consumer must remember to round; easy to forget
- Round inside each scorer function (`calculate_fundamental_score`, etc.) — couples a presentation concern to business logic
- `Score` type alias with `AfterValidator(lambda v: round(v, 1))` on every score field — rounding is guaranteed at model construction time, enforced by Pydantic, invisible to callers
**Decision:** `Score` type alias at the model level. One definition in `report.py`, applied to all six score fields across the four models. The pipeline and scorers produce any precision they like — the model always stores exactly one decimal place. No display layer or scorer needs to know about it.
**Outcome:** `Score = Annotated[float, AfterValidator(lambda v: round(v, 1))]` added to `report.py`. Applied to `FundamentalData.score`, `TechnicalData.score`, `PeerReport.weighted_score`, and `StockReport.fundamental_score / technical_score / weighted_score`.

---

## DEC-018 — Team hierarchy and sub-agent delegation protocol
**Raised by:** Eran after observing that Aria's commit was bundled into Claude's commit and her worklog was left unstaged
**Context:** As the team grew to include Aria as a specialist sub-agent, the chain of command for commits, approvals, and documentation was not clearly codified. Work was being silently absorbed into the wrong commit, and the delegation model was ambiguous.
**Decision:** Three-tier hierarchy, strictly enforced:
- **Eran (team lead)** — all authority. Approves all commits, all significant decisions. Nothing ships without his go-ahead.
- **Claude (lead developer)** — owns backend, protocol steps, architecture, and ALL project-level markdown (DECISIONS.md, GLOSSARY.md, ARCHITECTURE.md, QA.md, MCP_SERVER.md, LEARNING_MATERIAL.md). Coordinates with Aria. Manages all commits including Aria's when she is a sub-agent.
- **Aria (UI specialist)** — owns `src/stock_agent/ui/**` and her worklog only. Never touches project-level markdown — she flags needed updates to Claude.

**Sub-agent delegation protocol:**
- When Claude spawns Aria via the `Agent` tool (Mode 2), Aria cannot talk to Eran directly. Her output returns to Claude.
- Aria must always include a `COMMIT PROPOSAL` block in her sub-agent output — staged files + commit message in her voice.
- Claude presents the proposal to Eran. Only after Eran approves does Claude run `git commit` in Aria's name (with `Co-Authored-By: Aria <aria.stockagent@gmail.com>`).
- Claude must never silently bundle Aria's files into his own commit.

**Outcome:** `aria.md` updated with the two-mode invocation model. `SKILL.md` updated with mandatory COMMIT PROPOSAL block requirement.

---

## DEC-019 — `KeyPoint` model with sentiment over two flat lists for analyst observations
**Raised by:** Eran during report card review — wanted colored bullets distinguishing good vs bad news
**Options considered:**
- Two flat lists (`positive_points: list[str]`, `negative_points: list[str]`) — simple for the LLM, but forces every observation to be binary; no neutral factual context allowed
- `KeyPoint(text, sentiment)` model — one field, structured data; LLM classifies each point; neutral observations handled naturally; Aria renders bullet colour from `.sentiment`
**Decision:** `KeyPoint` model (Option B). The schema gives the LLM a clear contract, handles neutrals gracefully, and keeps `key_points` as a single field rather than splitting the analyst output across two. Aria maps `sentiment` to emerald/rose/gray bullet dots at render time.
**Outcome:** `KeyPoint` added to `report.py`. `StockReport.key_points` changed from `list[str]` to `list[KeyPoint]`. System prompt updated with sentiment classification guidance.

---

## DEC-024 — Separate Pydantic response schemas over raw ORM objects in HTTP endpoints
**Raised by:** Rex during Step 43 implementation
**Context:** FastAPI can accept SQLAlchemy ORM models directly as `response_model`. This avoids defining extra classes.
**Options considered:**
- Return raw ORM objects — fewer classes; but SQLAlchemy ORM instances carry internal state (`_sa_instance_state`) that is not serialisable, creating an undefined and fragile HTTP contract tightly coupled to the storage model
- Explicit Pydantic response schemas with `from_attributes=True` — full control over the HTTP contract; ORM model and API shape evolve independently; `model_validate(orm_record)` reads attributes directly with no intermediate dict mapping
**Decision:** Explicit response schemas. The HTTP contract must be stable and independent of storage decisions. `StockReportResponse` and `AnalysisJobResponse` expose only the fields callers need, keep `Decimal` for scores (no float drift), and decouple the API from future ORM changes.
**Outcome:** `StockReportResponse` and `AnalysisJobResponse` defined in `api.py`. Both use `model_config = {"from_attributes": True}`.

---

## DEC-025 — `GET /jobs` returns `200 + []` for empty collections, never `404`
**Raised by:** Rex during Step 43 implementation
**Context:** When no jobs exist, `list_recent_jobs()` returns `[]`. The question is whether to return `404` or `200 + []`.
**Options considered:**
- `404 Not Found` — signals "nothing here"; but misleads clients into thinking the endpoint doesn't exist, conflating an empty collection with a missing resource
- `200 OK + []` — correct REST semantics; the endpoint exists, the collection is just empty
**Decision:** `200 + []`. REST convention is clear: `404` is for missing resources (a specific ticker with no report), not empty collections. A collection endpoint always exists — it just has zero items. Consistent with `GET /reports/{ticker}` which does return `404` when a specific resource is missing.
**Outcome:** `GET /jobs` route handler returns the list from `list_recent_jobs()` directly — FastAPI serialises `[]` as a `200` response.

---

## DEC-023 — `Numeric(4, 1)` over `Float` for score columns in `StockReportRecord`
**Raised by:** Eran during Step 42 documentation review
**Context:** Score columns (`fundamental_score`, `technical_score`, `weighted_score`) store decimal values in the range 1.0–10.0. The naive choice is `Float` — it maps directly to Python `float` and requires no conversion.
**Options considered:**
- `Float` — simple, no conversion needed; but IEEE 754 binary fractions mean 7.1 stored as a float can come back as 7.09999999999999964 from PostgreSQL — unacceptable for financial scores that appear in API responses, UI gauges, and filter queries
- `Numeric(4, 1)` with `Decimal` — PostgreSQL stores exact decimals; 7.1 always comes back as 7.1; requires explicit conversion from Python `float` before insert
**Decision:** `Numeric(4, 1)` with `Decimal` conversion. For financial scores, precision drift is a correctness issue, not a minor concern — a score of 7.1 must be 7.1 everywhere: in the DB, in the API response, in the UI gauge, and in filter queries. The conversion overhead is negligible. `save_report()` converts via `Decimal(str(round(score, 1)))` — going through `str()` first avoids inheriting any float imprecision before the value reaches the database. See QA.md Q40 for the full conversion explanation.
**Outcome:** All three score columns defined as `Numeric(4, 1)` in `models.py`. `save_report()` in `crud.py` converts scores via `Decimal(str(round(score, 1)))` on every insert.

---

## DEC-022 — Denormalized score columns in `StockReportRecord` for filter and sort performance
**Raised by:** Eran during Step 42 documentation review
**Context:** `StockReportRecord` stores the full `StockReport` as a JSON blob in `report_json`. Scores and recommendation are already inside that JSON — they could be read from there at query time.
**Options considered:**
- JSON-only storage — single source of truth, no duplication; but finding all BUY stocks above score 8 requires pulling every JSON blob, deserialising each one in Python, and filtering in application code — does not scale
- Denormalized typed columns alongside JSON — `fundamental_score`, `technical_score`, `weighted_score`, `recommendation` stored as `Numeric(4,1)` and `String` columns in addition to `report_json`; PostgreSQL handles the entire filter in a single indexed query
**Decision:** Denormalized columns (Option B). `report_json` remains the source of truth for display and full report retrieval. The score and recommendation columns are denormalized copies used purely for filtering and sorting. The cost is storing the scores twice; for read-heavy filter and sort patterns this is absolutely worth it.
```sql
-- With denormalized columns: fast, indexed, handled entirely by Postgres
SELECT * FROM stock_reports WHERE weighted_score > 8.0 AND recommendation = 'BUY';

-- Without: pull every row, parse JSON in Python, filter in application code
```
**Outcome:** `StockReportRecord` has both `report_json` (JSON) and `fundamental_score`, `technical_score`, `weighted_score`, `recommendation` as dedicated typed columns. `save_report()` in `crud.py` populates both on every insert.

---

## DEC-021 — `db/crud.py` as a Facade over SQLAlchemy
**Raised by:** Eran during Step 42 documentation review
**Context:** All DB operations could be written inline inside FastAPI route handlers or Celery tasks — SQLAlchemy sessions are available in both contexts.
**Options considered:**
- Inline DB calls in route handlers and tasks — fewer files, but each caller duplicates `select()` / `session.add()` / `db.refresh()` logic and is tightly coupled to the ORM implementation
- Dedicated `crud.py` module with intention-revealing functions — all SQLAlchemy complexity in one place; callers see `create_job(db, ticker)` not the machinery behind it
**Decision:** Dedicated CRUD module (Facade pattern). The facade gives every database operation a single, testable home. Route handlers, Celery tasks, and the NiceGUI layer all call the same functions without knowing how data is stored. Changing a query strategy or adding caching touches one file, not every caller. Each CRUD function is independently testable with an in-memory SQLite session — no HTTP server or worker required.
**Outcome:** `db/crud.py` is the only layer that writes SQLAlchemy queries. All other layers call CRUD functions with an injected `AsyncSession`.

---

## DEC-020 — Alembic reads DATABASE_URL from Settings at runtime, not from alembic.ini
**Raised by:** Rex (Step 38 backend infrastructure setup)
**Context:** `alembic init` generates `alembic.ini` with a `sqlalchemy.url` placeholder. The naive approach is to put the database URL there — but this is a plaintext file committed to the repo.
**Options considered:**
- Hardcode URL in `alembic.ini` — simple, but puts credentials in the repo and duplicates a value that already lives in `config.py`
- Inject URL at runtime via `migrations/env.py` — `env.py` imports `settings` from `stock_agent.config` and calls `config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)` before Alembic reads it
**Decision:** Runtime injection via `env.py`. `alembic.ini` has no URL — the `sqlalchemy.url` line is replaced with a comment explaining where the value comes from. Single source of truth: `DATABASE_URL` is always `config.py` → environment variable.
**Outcome:** `migrations/env.py` imports `stock_agent.config.settings`. `alembic.ini` `sqlalchemy.url` is nulled out. No secrets in any committed file.

