# Engineering Tasks & Backlog

Tasks identified during development that fall outside the 62-step Atomic Commit Protocol.
Logged by Eran (engineer) during active development — evidence of human-driven design
decisions, code review, and iterative improvement made in collaboration with Claude.

---

## Status Legend
- `[ ]` Open
- `[~]` In Progress
- `[x]` Done

---

## Backlog

### Output & Reporting

- [~] **TASK-006** — Replace `summary: str` with `key_points: list[str]` in `StockReport` for structured analyst output
  **Raised by:** Eran after observing the analyst summary renders as one unreadable paragraph
  **Context:** The LLM produces a free-form narrative string with no structural guidance. The UI has no way to break it up meaningfully. Changing the field to a list gives the LLM a clear schema contract and makes rendering trivial.
  **Approach:** Option A — model field change + system prompt update + UI re-render via Aria.
  **Acceptance criteria:**
  - `StockReport.summary` renamed to `key_points: list[str]` with `Field(description=...)`
  - Agent system prompt updated to instruct the LLM to produce 4–6 concise bullet points
  - `report_card.py` updated by Aria to render the list as bullet points

- [ ] **TASK-001** — Add `catalysts`, `risk_flags`, and `news_summary` fields to `StockReport`
  **Raised by:** Eran during Step 28 CLI testing (live ONDS run)
  **Context:** Eran noticed that while the `summarize_news_and_extract_risks` tool is called
  by the agent, its output only feeds into the LLM's reasoning and gets collapsed into the
  `summary` string. Headlines, catalysts, and risk flags are never surfaced in the structured
  output — making it impossible to display them in the UI or inspect them programmatically.
  **Acceptance criteria:**
  - `StockReport` gains three new fields: `catalysts: list[str]`, `risk_flags: list[str]`, `news_summary: str`
  - CLI output includes all three fields
  - UI (Step 34+) can render headlines and risk flags in the report card
  **Suggested timing:** After Step 30 (peer analysis) — all pipeline tools will be wired by then.

### Data Pipeline

- [ ] **TASK-003** — Replace non-functional `fetch_industry_peers` with a working peer discovery strategy
  **Raised by:** Eran during Step 30 testing
  **Context:** yfinance's `industryPeers` field has been silently removed from the API. `fetch_industry_peers` always returns `[]`, making `get_peer_reports` a no-op. The Step 30 logic is architecturally correct but the peer data source is broken. Eran decided not to block Phase 5 completion over a data provider gap — deferred for a dedicated strategy discussion.
  **Options considered:**
  - DuckDuckGo peer search — dynamic but fragile (web scraping, ticker parsing)
  - Static industry lookup table in `config.py` — reliable but needs manual maintenance
  - Third-party financial API (e.g. Financial Modeling Prep, Polygon.io) — best coverage, adds a dependency
  **Acceptance criteria:**
  - `fetch_industry_peers(ticker)` returns a non-empty `list[str]` of valid peer tickers for mainstream stocks (e.g. AAPL, NVDA, MSFT)
  - Max 5 peers enforced (slicing happens in `get_peer_reports`, not in the fetcher)
  - Graceful fallback to `[]` if peer discovery fails — never crashes the main analysis pipeline
  - `fetch_industry_peers` remains the only place peer discovery logic lives (no leakage into agent tools)
  **Suggested timing:** After Phase 5 is complete (Step 30+). Requires a dedicated strategy decision before implementation.

### UI Bug Fixes

- [x] **TASK-005** — Fix `AttributeError: 'GenericEventArguments' object has no attribute 'value'` in chip toggle handler
  **Raised by:** Eran during live server testing (strategy panel chip clicks)
  **Context:** `strategy_panel.py` `on_select` handler used `e.value` to read the chip's selected state. The `update:selected` event on `ui.chip(selectable=True)` delivers its boolean payload via `e.args`, not `e.value` — `e.value` only exists on `ValueChangeEventArguments` (sliders, checkboxes, inputs). Every chip click raised an unhandled `AttributeError`.
  **Fix:** Changed `if e.value:` → `if e.args:` in `on_select`. One-line fix in `strategy_panel.py:110`.
  **Acceptance criteria:** Chip toggles update `active_set` and swap chip color without errors.

### MCP Server

- [x] **TASK-002** — Add `score_ticker` tool to the MCP server that mimics the CLI input/output without invoking the cloud LLM
  **Raised by:** Eran after Step 28 CLI testing
  **Context:** Eran wanted a way to trigger the full scoring pipeline (fundamentals + technicals + weighted score + recommendation) directly from Claude mid-conversation, without the cost and latency of a cloud LLM call. Since the MCP server is a devops/inspection tool, deterministic output is sufficient — the `summary` narrative is not needed here.
  **Approach chosen:** Option B (lightweight) — reuse the deterministic scorers from `inspect_ticker`, add `fundamental_weight` and `technical_weight` as optional params, compute `weighted_score` and `recommendation` locally.
  **Acceptance criteria:**
  - New `score_ticker(ticker, fundamental_weight, technical_weight)` tool added to `stock_mcp_server.py`
  - Returns fundamentals, technicals, weighted score, and recommendation label — no LLM call
  - `MCP_SERVER.md` updated with the new tool and a changelog entry
  **Suggested timing:** Implement before Step 29.

---

## Completed

- [x] **TASK-002** — `score_ticker` MCP tool implemented in `stock_mcp_server.py`. `MCP_SERVER.md` updated with tool reference and v0.3.0 changelog entry.
