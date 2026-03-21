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
