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

---

## Completed

*(Tasks move here once merged into the codebase)*
