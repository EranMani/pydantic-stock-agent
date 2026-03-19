"""MCP server for the Autonomous PydanticAI Stock Analyst Agent.

Exposes pipeline and development workflow tools to Claude via the Model Context
Protocol. Claude calls these tools mid-conversation — no manual test scripts or
copy-pasting terminal output required.

Run via: uv run python stock_mcp_server.py
Configured in .mcp.json at the project root.

Windows IOCP notes
------------------
Two issues were diagnosed and fixed here:

1. subprocess stdin inheritance deadlock
   subprocess.run() without stdin=subprocess.DEVNULL inherits the MCP server's
   Windows IOCP (overlapped) stdin pipe. Any child process holding an open handle
   to that pipe blocks anyio's async stdin reader permanently. Fix: always pass
   stdin=subprocess.DEVNULL and wrap the call in asyncio.to_thread() so the event
   loop is never blocked.

2. Heavy deferred imports blocking the event loop
   Importing pandas / yfinance / pandas_ta inside an async tool function blocks
   the event loop for ~2 seconds while the import runs. On Windows this prevents
   anyio's zero-capacity memory stream rendezvous from completing, so the tool
   response is never flushed to stdout. Fix: import all pipeline modules at module
   level, before mcp.run() calls anyio.run(). The ~2s cost is paid once at startup,
   not inside a live tool call.
"""

import asyncio
import re
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Pipeline modules — imported at module level so the event loop is never blocked
# during tool execution. The ~2s import cost is paid once before anyio.run() starts.
from stock_agent.models.context import ScoringStrategy
from stock_agent.pipelines.technical.core_data import fetch_ohlcv
from stock_agent.scoring.technical_scorer import calculate_technical_score

# Server name shown in Claude's tool list
mcp = FastMCP("stock-devops")

# Repo root — used for git commands and protocol file reads
_REPO_ROOT = Path(__file__).parent
_PROTOCOL_FILE = _REPO_ROOT / ".claude" / "commit-protocol.md"


# ---------------------------------------------------------------------------
# Tool 1 — get_current_step
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_current_step() -> str:
    """Read the git log and commit protocol to report exactly where we are in the 62-step build process.

    Returns the current step number, its commit message, the phase name, and the
    last commit made. Eliminates the startup ritual of re-reading CLAUDE.md and
    checking git log at the start of every session.
    """
    # asyncio.to_thread: keeps the event loop free while git runs.
    # stdin=DEVNULL: prevents git from inheriting the MCP server's IOCP stdin pipe
    # (see module docstring — Issue 1).
    git_result = await asyncio.to_thread(
        subprocess.run,
        ["git", "log", "--oneline", "-30"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    recent_commits = git_result.stdout.strip().splitlines()
    last_commit_msg = recent_commits[0].split(" ", 1)[1] if recent_commits else "none"

    protocol_text = _PROTOCOL_FILE.read_text(encoding="utf-8")

    # Parse all (step_num, commit_msg, phase) triples from the protocol file
    protocol_steps: list[tuple[int, str, str]] = []
    current_phase = ""
    for line in protocol_text.splitlines():
        if line.startswith("## Phase"):
            current_phase = line.strip().lstrip("# ").strip()
        match = re.match(r"### Step (\d+) — `(.+?)`", line)
        if match:
            protocol_steps.append((int(match.group(1)), match.group(2), current_phase))

    # Find highest completed step whose commit message appears in git log
    committed_messages = {c.split(" ", 1)[1] for c in recent_commits}
    last_completed_step = 0
    for step_num, commit_msg, _ in protocol_steps:
        if commit_msg in committed_messages and step_num > last_completed_step:
            last_completed_step = step_num

    next_step_index = last_completed_step  # 0-based index into protocol_steps list
    if next_step_index < len(protocol_steps):
        next_step_num, next_commit_msg, next_phase = protocol_steps[next_step_index]
        return (
            f"Current step:   {next_step_num} of {len(protocol_steps)}\n"
            f"Phase:          {next_phase}\n"
            f"Commit message: {next_commit_msg}\n"
            f"Last commit:    {last_commit_msg}\n"
            f"Completed:      {last_completed_step} steps\n"
            f"Remaining:      {len(protocol_steps) - last_completed_step} steps"
        )
    return f"All {len(protocol_steps)} steps completed!\nLast commit: {last_commit_msg}"


# ---------------------------------------------------------------------------
# Tool 2 — analyze_ticker
# ---------------------------------------------------------------------------

@mcp.tool()
async def analyze_ticker(ticker: str) -> str:
    """Run the full technical pipeline on a ticker and return a scored summary.

    Fetches OHLCV data via yfinance, computes all moving averages, runs the
    Minervini Trend Template and VCP checks, and returns a formatted TechnicalData
    summary. Replaces the manual test scripts written after each build step.
    """
    df = await fetch_ohlcv(ticker)
    strategy = ScoringStrategy()  # default: trend_template + vcp
    data = calculate_technical_score(df, strategy)

    trend = "PASS" if data.trend_template_passed else "FAIL"
    close = df["Close"].iloc[-1]

    return (
        f"{ticker} Technical Analysis\n"
        f"{'-' * (len(ticker) + 21)}\n"
        f"Last Close:      ${close:.2f}\n"
        f"SMA 50:          ${data.sma_50:.2f}\n"
        f"SMA 150:         ${data.sma_150:.2f}\n"
        f"SMA 200:         ${data.sma_200:.2f}\n"
        f"52w High:        ${data.high_52w:.2f}\n"
        f"52w Low:         ${data.low_52w:.2f}\n"
        f"Trend Template:  {trend}\n"
        f"VCP Detected:    {data.vcp_detected}\n"
        f"Technical Score: {data.score:.2f}"
    )


# ---------------------------------------------------------------------------
# Tool 3 — compare_tickers
# ---------------------------------------------------------------------------

@mcp.tool()
async def compare_tickers(tickers: list[str]) -> str:
    """Run analyze_ticker concurrently on a list of tickers and return a ranked comparison table.

    Fetches and scores all tickers in parallel via asyncio.gather, then sorts
    results by technical score descending. Replaces multi-ticker test loops.
    """
    strategy = ScoringStrategy()

    async def _score_one(ticker: str) -> tuple[str, float, bool, bool, float]:
        """Return (ticker, score, trend_template, vcp, close) for one ticker."""
        try:
            df = await fetch_ohlcv(ticker)
            data = calculate_technical_score(df, strategy)
            close = float(df["Close"].iloc[-1])
            return ticker, data.score, data.trend_template_passed, data.vcp_detected, close
        except Exception:
            return ticker, 0.0, False, False, 0.0

    results = await asyncio.gather(*[_score_one(t) for t in tickers])
    ranked = sorted(results, key=lambda r: r[1], reverse=True)

    header = f"{'Ticker':<8}  {'Score':<7}  {'Trend Template':<16}  {'VCP':<7}  {'Close'}\n"
    divider = f"{'------':<8}  {'------':<7}  {'---------------':<16}  {'------':<7}  {'------'}\n"
    rows = ""
    for ticker, score, trend, vcp, close in ranked:
        trend_str = "PASS" if trend else "FAIL"
        rows += f"{ticker:<8}  {score:<7.2f}  {trend_str:<16}  {str(vcp):<7}  ${close:.2f}\n"

    return header + divider + rows.rstrip()


# ---------------------------------------------------------------------------
# Tool 4 — run_tests
# ---------------------------------------------------------------------------

@mcp.tool()
async def run_tests() -> str:
    """Execute the full pytest suite and return the output.

    Runs `uv run pytest` from the repo root and returns stdout + stderr.
    Lets Claude verify nothing is broken mid-conversation without the user
    switching to a terminal.
    """
    # asyncio.to_thread: pytest can take up to 2 minutes — blocking the event
    # loop that long would stall all MCP communication.
    # stdin=DEVNULL: same Windows IOCP deadlock prevention as get_current_step.
    result = await asyncio.to_thread(
        subprocess.run,
        ["uv", "run", "pytest", "--tb=short"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=120,
    )
    output = result.stdout + result.stderr
    return output.strip() if output.strip() else "No output from pytest."


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # stdio transport — Claude Code communicates via stdin/stdout
    mcp.run(transport="stdio")
