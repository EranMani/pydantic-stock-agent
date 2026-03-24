# Engineering Tasks & Backlog

Out-of-protocol tasks logged by Eran during active development.

**Status:** `[ ]` Open · `[~]` In Progress · `[x]` Done

---

## Task Index

| ID | Status | Title | Area |
|---|---|---|---|
| TASK-001 | `[ ]` | Add `catalysts`, `risk_flags`, `news_summary` to `StockReport` | Output |
| TASK-002 | `[x]` | Add `score_ticker` tool to MCP server | MCP |
| TASK-003 | `[ ]` | Fix non-functional `fetch_industry_peers` peer discovery | Pipeline |
| TASK-004 | `[x]` | Five Quasar component upgrades across UI suite | UI |
| TASK-005 | `[x]` | Fix `e.value` → `e.args` in chip toggle handler | UI Bug |
| TASK-006 | `[x]` | Replace `summary: str` with `key_points: list[str]` | Output |
| TASK-007 | `[x]` | Add `company_name: str` to `StockReport` and render in verdict panel | Output |
| TASK-008 | `[x]` | Replace `key_points: list[str]` with `list[KeyPoint]` for sentiment bullets | Output |
| TASK-009 | `[x]` | Remove numeric score labels from QLinearProgress bars | UI |
| TASK-010 | `[ ]` | Add FK from `StockReportRecord.job_id` → `AnalysisJobRecord.job_id` | DB |

---

## Open Tasks

### TASK-001 — Add `catalysts`, `risk_flags`, `news_summary` to `StockReport`
**Raised by:** Eran during Step 28 CLI testing (live ONDS run)

The `summarize_news_and_extract_risks` tool output collapses into LLM reasoning only — headlines, catalysts, and risk flags are never surfaced in the structured output. Three new fields needed: `catalysts: list[str]`, `risk_flags: list[str]`, `news_summary: str`. CLI and UI (Step 34+) must render all three.

**Timing:** After Step 30 (peer analysis). All pipeline tools wired by then.

---

### TASK-003 — Fix non-functional `fetch_industry_peers`
**Raised by:** Eran during Step 30 testing

yfinance's `industryPeers` field was silently removed — `fetch_industry_peers` always returns `[]`, making `get_peer_reports` a no-op. Options: DuckDuckGo peer search (fragile), static lookup table in `config.py` (reliable, manual), or third-party API (best coverage, adds dependency). Must gracefully fall back to `[]` on failure.

**Timing:** After Phase 5. Requires a dedicated strategy decision before implementation.

---

### TASK-010 — Add FK from `StockReportRecord.job_id` → `AnalysisJobRecord.job_id`
**Raised by:** Eran during Step 42 review

`save_report()` accepts `job_id` but never uses it — `StockReportRecord` has no `job_id` column, so the two tables are unlinked. Fix: add `job_id: String(36)` with `ForeignKey("analysis_jobs.job_id")` to `StockReportRecord`, add `relationship()` on both models, populate it in `save_report()`, and write a new Alembic migration. Eran confirmed Option B (proper FK with relational integrity) is the right approach.

**Acceptance criteria:** `report.job` ORM traversal works; `job.report` ORM traversal works; migration upgrades and downgrades cleanly; existing tests still pass.

**Timing:** Deferred — implement before Step 43 (API endpoints) so the `GET /reports/{ticker}` response can include job metadata.
