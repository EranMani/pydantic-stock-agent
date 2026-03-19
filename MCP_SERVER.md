# Stock Agent MCP Server

A Model Context Protocol server that exposes the stock analysis pipeline and development workflow tools directly to Claude. Instead of writing test scripts manually or copy-pasting terminal output, Claude calls these tools mid-conversation and returns live results instantly.

---

## Setup

### 1. Project MCP config

The server is configured via `.mcp.json` at the project root (already checked in). Claude Code automatically detects this file when opening the project directory:

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

### 2. Restart Claude Code

Claude spawns the server as a subprocess on startup and communicates over stdio. No HTTP server or open ports required.

### 3. Verify

Ask Claude: *"what tools do you have available?"* — the stock-devops tools should appear in the list.

---

## Tools Reference

### `get_current_step`

**Purpose:** Reads the git log and commit protocol to return exactly where we are in the 62-step build process. Eliminates the startup ritual of re-reading CLAUDE.md and checking git log at the start of every session.

**Inputs:** none

**Output:** Plain text summary:
```
Current step: 25
Commit message: feat: initialize main PydanticAI Agent with system prompt and cloud model
Phase: 5 — Agent Assembly & CLI
Last commit: feat: calculate final technical score (1-10) based on Trend Template and VCP
```

**When Claude uses it:** Automatically at the start of sessions where protocol progress is relevant.

---

### `analyze_ticker`

**Purpose:** Runs the full technical pipeline on any ticker — fetches OHLCV data, computes all moving averages, runs trend template and VCP checks, and returns a scored `TechnicalData` summary. Replaces the manual test scripts written after each build step.

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `ticker` | `str` | Stock ticker symbol (e.g. `"AAPL"`) |

**Output:** Formatted text summary:
```
AAPL Technical Analysis
-----------------------
Last Close:     $169.12
SMA 50:         $182.45
SMA 150:        $191.23
SMA 200:        $185.67
52w High:       $237.23
52w Low:        $164.08
Trend Template: FAIL
VCP Detected:   False
Technical Score: 1.00
```

**When Claude uses it:** Any time a live ticker test is needed during development or analysis discussion.

---

### `compare_tickers`

**Purpose:** Runs `analyze_ticker` concurrently on a list of tickers and returns a ranked comparison table sorted by technical score descending. Replaces multi-ticker test loops.

**Inputs:**
| Parameter | Type | Description |
|---|---|---|
| `tickers` | `list[str]` | List of ticker symbols (e.g. `["ONDS", "RKLB", "EOSE"]`) |

**Output:** Ranked comparison table:
```
Ticker  Score   Trend Template  VCP     Close
------  ------  --------------  ------  ------
ONDS    10.00   PASS            True    $10.83
RKLB     4.38   FAIL            True    $69.48
EOSE     1.00   FAIL            False    $5.28
```

**When Claude uses it:** Watchlist screening, comparing setups side-by-side, validating pipeline behaviour across diverse tickers.

---

### `run_tests`

**Purpose:** Executes the full pytest suite and returns the output. Lets Claude verify nothing is broken mid-conversation without the user switching to a terminal.

**Inputs:** none

**Output:** Raw pytest output including pass/fail counts and any error tracebacks.

**When Claude uses it:** After implementing a step, before committing, or when debugging a failing test.

---

## Windows Compatibility Notes

FastMCP uses `anyio` under the hood to run its event loop and flush tool responses to stdout via a **zero-capacity memory stream rendezvous** — both sides (writer and reader) must be ready at the same moment for the flush to complete. On Linux/macOS this is forgiving; on Windows it is not, because Windows uses **IOCP (I/O Completion Ports)** for async I/O, which is less tolerant of event-loop stalls. Two categories of mistakes will silently hang every tool call on Windows:

---

### Rule 1 — Never block the event loop inside a tool function

**What goes wrong:** Importing heavy modules (`pandas`, `yfinance`, `pandas_ta`) inside an `async def` tool function blocks the asyncio event loop for ~2 seconds while the C-extensions load. During that 2-second block, `anyio`'s stdout rendezvous cannot complete, so the tool response is queued but **never flushed** — the call hangs indefinitely.

**The rule:** All imports used by tool functions must live at **module level**, executed once before `mcp.run()` starts the event loop. Accepting a slightly longer server startup (~2s) is the correct trade-off.

```python
# WRONG — blocks the event loop on first call
@mcp.tool()
async def analyze_ticker(ticker: str) -> str:
    from stock_agent.pipelines.technical.core_data import fetch_ohlcv  # 2s block
    ...

# CORRECT — import at module level, event loop never stalls
from stock_agent.pipelines.technical.core_data import fetch_ohlcv

@mcp.tool()
async def analyze_ticker(ticker: str) -> str:
    ...
```

The same applies to any other CPU-bound or import-heavy work. If you must do blocking work inside a tool, offload it with `asyncio.to_thread()`.

---

### Rule 2 — Always pass `stdin=subprocess.DEVNULL` to subprocess calls

**What goes wrong:** The MCP server communicates with Claude over **stdio** — its stdin is an IOCP overlapped pipe managed by `anyio`. When a child process (`git`, `pytest`, etc.) is spawned without redirecting stdin, it **inherits that pipe handle**. While the child holds the handle open, `anyio`'s async stdin reader is permanently blocked, so the tool call never returns.

**The rule:** Every `subprocess.run()` (or `subprocess.Popen`) call in this server must include `stdin=subprocess.DEVNULL`. Additionally, wrap subprocess calls in `asyncio.to_thread()` so they don't block the event loop.

```python
# WRONG — child inherits the IOCP pipe, anyio stdin reader hangs forever
result = subprocess.run(["git", "log"], capture_output=True, text=True)

# CORRECT — pipe is closed for the child; subprocess runs off the event loop
result = await asyncio.to_thread(
    subprocess.run,
    ["git", "log"],
    capture_output=True,
    text=True,
    stdin=subprocess.DEVNULL,
)
```

---

### Summary checklist for adding a new tool

| Concern | Required action |
|---|---|
| Heavy imports (pandas, yfinance, etc.) | Move to module level — never inside the tool function |
| CPU-bound or blocking work | Wrap with `asyncio.to_thread()` |
| Any `subprocess.run()` call | Add `stdin=subprocess.DEVNULL` + wrap in `asyncio.to_thread()` |
| Tool function signature | Use `async def` — FastMCP natively awaits tool coroutines |

---

## Changelog

### v0.1.3 — 2026-03-19

**Bug fix — all 4 tools hanging indefinitely on Windows (two root causes)**

#### Root cause 1 — subprocess stdin inheritance (affects `get_current_step`, `run_tests`)
`subprocess.run()` without `stdin=subprocess.DEVNULL` inherits the MCP server's
Windows IOCP (overlapped) stdin pipe. While `git` or `pytest` hold an open handle
to that pipe, `anyio`'s async stdin reader is permanently blocked — the tool call
never returns a response.

**Fix:** Added `stdin=subprocess.DEVNULL` to both `subprocess.run()` calls and
converted both tools to `async def` with `asyncio.to_thread()` so subprocess
execution never blocks the event loop.

#### Root cause 2 — heavy deferred imports blocking the event loop (affects `analyze_ticker`, `compare_tickers`)
Importing `pandas` / `yfinance` / `pandas_ta` inside an `async def` tool function
blocks the asyncio event loop for ~2 seconds while the imports execute. On Windows,
this 2-second block prevents `anyio`'s zero-capacity memory stream rendezvous from
completing, so the tool response is queued but never flushed to stdout.

**Fix:** Moved all pipeline imports (`ScoringStrategy`, `fetch_ohlcv`,
`calculate_technical_score`) to module level. They now execute before `mcp.run()`
calls `anyio.run()`, so the event loop is never blocked during tool execution.
Server startup is ~2s longer, but all tool calls are now fast and reliable.

**Additional:** Removed the now-redundant `_async_analyze_ticker` and
`_async_compare_tickers` helper functions — the tool functions are now self-contained.

---

### v0.1.2 — 2026-03-19

**Bug fix — heavy imports at module level caused 5+ minute MCP server startup**

#### Fixed
- Moved `from stock_agent.models.context import ScoringStrategy`, `from stock_agent.pipelines.technical.core_data import fetch_ohlcv`, and `from stock_agent.scoring.technical_scorer import calculate_technical_score` from module-level into `_async_analyze_ticker` and `_async_compare_tickers` — the two functions that actually need them. This reduces server startup from 5+ minutes to ~2 seconds, making `get_current_step` and `run_tests` usable immediately without waiting for pandas/yfinance/pandas-ta to load.

**Tools unaffected:** Behaviour of all 4 tools is unchanged; only the import timing changed.

---

### v0.1.1 — 2026-03-19

**Bug fix — async tools crash under FastMCP's running event loop**

#### Fixed
- `analyze_ticker` — converted from `def` to `async def`; replaced `asyncio.run(_async_analyze_ticker(...))` with a direct `await` call. `asyncio.run()` raises `RuntimeError` when called from within an already-running event loop (FastMCP's own loop), which caused every ticker analysis call to fail.
- `compare_tickers` — same fix: converted to `async def` and replaced `asyncio.run(_async_compare_tickers(...))` with `await`. FastMCP natively supports async tool functions, so no bridge is needed.

**Tools unaffected:** `get_current_step` and `run_tests` are synchronous (git/subprocess I/O only) and required no changes.

---

### v0.1.0 — 2026-03-19

**First release — 4 tools focused on development workflow acceleration**

#### Added
- `get_current_step` — reads git log + commit-protocol.md to instantly report where we are in the 62-step protocol; eliminates the startup ritual of re-reading CLAUDE.md and checking git log at the start of every session
- `analyze_ticker` — runs the full technical pipeline (OHLCV fetch → moving averages → trend template → VCP → score) on any ticker; replaces the manual test scripts we write after each build step
- `compare_tickers` — runs `analyze_ticker` concurrently on a list of tickers via `asyncio.gather` and returns a ranked table; replaces multi-ticker test loops
- `run_tests` — executes `uv run pytest` and returns output; lets Claude verify test results without the user switching to a terminal

**Why this batch:**
These four tools were chosen for maximum day-to-day impact during active protocol development. They eliminate the four most repetitive manual actions in our workflow: checking progress, running ticker tests, comparing tickers, and verifying tests. Every subsequent session benefits from all four immediately.
