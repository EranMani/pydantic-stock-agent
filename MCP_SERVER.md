# Stock Agent MCP Server

A Model Context Protocol server exposing the stock analysis pipeline and development workflow tools directly to Claude — no terminal switching, no manual test scripts.

---

## Setup

Add to `.mcp.json` at the project root (already checked in). Claude Code detects this automatically on project open and spawns the server as a subprocess over stdio.

```json
{
  "mcpServers": {
    "stock-devops": {
      "command": "uv",
      "args": ["run", "python", "stock_mcp_server.py"],
      "cwd": "D:/AI/_My_Projects/pydantic-stock-agent"
    }
  }
}
```

Restart Claude Code after any change to `.mcp.json` — the server loads once at startup.

---

## Tools Reference

| Tool | Purpose | Inputs | When Claude uses it |
|---|---|---|---|
| `get_current_step` | Reports current position in the 62-step build protocol by reading git log + commit-protocol.md | none | Start of every session |
| `analyze_ticker` | Full technical pipeline: OHLCV → MAs → Trend Template → VCP → score | `ticker: str` | Live ticker tests during development |
| `compare_tickers` | Runs `analyze_ticker` concurrently on multiple tickers, returns ranked table | `tickers: list[str]` | Watchlist screening, side-by-side comparison |
| `run_tests` | Executes `uv run pytest` and returns output | none | After implementing a step, before committing |
| `inspect_ticker` | Full pipeline wiring test: fundamentals + technicals + MA signal + Ollama news | `ticker: str` | Validating pipeline wiring after a build step |
| `score_ticker` | Deterministic weighted scoring without cloud LLM | `ticker: str`, `fundamental_weight: float = 0.5`, `technical_weight: float = 0.5` | Verifying scoring pipeline mid-conversation |

### Output samples

**`analyze_ticker("AAPL")`**
```
Last Close: $169.12 · SMA 50: $182.45 · SMA 150: $191.23 · SMA 200: $185.67
52w High: $237.23 · 52w Low: $164.08 · Trend Template: FAIL · VCP: False · Score: 1.00
```

**`score_ticker("ONDS", fundamental_weight=0.3, technical_weight=0.7)`**
```
ONDS — Ondas Holdings Inc.
FUNDAMENTAL: 5.50/10 (w:0.3) | P/E: N/A · Beta: 2.58 · RevGrowth: +5.8%
TECHNICAL:  10.00/10 (w:0.7) | Trend Template: PASS · VCP: True
WEIGHTED: 8.65/10 → BUY
```

---

## Windows Compatibility — Rules for New Tools

FastMCP uses `anyio` with **IOCP (I/O Completion Ports)** on Windows — two rules are non-negotiable:

**Rule 1 — Never block the event loop inside a tool function.**
All imports of heavy modules (`pandas`, `yfinance`, `pandas_ta`) must live at **module level**, executed before `mcp.run()`. Importing inside an `async def` tool blocks the event loop for ~2s, preventing `anyio`'s stdout rendezvous from completing — the call hangs indefinitely.

**Rule 2 — Always pass `stdin=subprocess.DEVNULL` to subprocess calls.**
The MCP server's stdin is an IOCP overlapped pipe. A child process (`git`, `pytest`) that inherits this handle blocks `anyio`'s async stdin reader permanently. Also wrap in `asyncio.to_thread()` to keep subprocess calls off the event loop.

**Checklist for adding a new tool:**

| Concern | Required action |
|---|---|
| Heavy imports (pandas, yfinance, etc.) | Module level — never inside the tool function |
| CPU-bound or blocking work | `asyncio.to_thread()` |
| Any `subprocess.run()` call | `stdin=subprocess.DEVNULL` + `asyncio.to_thread()` |
| Tool function signature | `async def` — FastMCP natively awaits coroutines |

---

## Changelog

| Version | Date | Change |
|---|---|---|
| v0.3.1 | 2026-03-22 | **Fix:** `get_current_step` returning Step 1 — increased git log limit from `-30` to `-200`. Non-protocol commits had pushed protocol steps out of the 30-commit window. Takes effect on next session restart. |
| v0.3.0 | 2026-03-20 | **Add:** `score_ticker(ticker, fundamental_weight, technical_weight)` — deterministic weighted scoring without LLM call. Proposed by Eran for mid-conversation pipeline verification. |
| v0.2.0 | 2026-03-20 | **Add:** `inspect_ticker(ticker)` — full pipeline wiring test (fundamentals + technicals + MA signal + Ollama news) in one call. Replaces `scripts/test_agent_wiring.py`. |
| v0.1.3 | 2026-03-19 | **Fix:** All 4 tools hanging on Windows. Two root causes: subprocess stdin inheritance (added `DEVNULL`); heavy deferred imports blocking event loop (moved to module level). |
| v0.1.2 | 2026-03-19 | **Fix:** Heavy module-level imports caused 5+ minute server startup. Moved pipeline imports into tool functions (subsequently reversed in v0.1.3). |
| v0.1.1 | 2026-03-19 | **Fix:** `analyze_ticker` / `compare_tickers` crashing under FastMCP's running event loop. Converted from `def` + `asyncio.run()` to `async def` + `await`. |
| v0.1.0 | 2026-03-19 | **Init:** `get_current_step`, `analyze_ticker`, `compare_tickers`, `run_tests`. |
