# Autonomous PydanticAI Stock Analyst Agent

> **Status: Work In Progress** — actively developed following a 62-step Atomic Commit Protocol. Not yet production-ready.

## What Is This?

An autonomous stock analysis agent that combines deterministic financial data pipelines with structured LLM reasoning to produce actionable stock reports. The agent fetches real market data, computes technical indicators, scores stocks across fundamental and technical dimensions, and generates a structured `StockReport` — all without letting the LLM touch raw numbers or perform calculations.

The core design principle: **the LLM reasons over pre-computed data, never computes it**.

## Why I built it
Built out of personal need — I'm a swing trader, and I wanted a tool that could analyze stocks against specific technical and fundamental conditions and tell me whether a setup is worth entering. What started as a personal trading tool became a production-grade AI engineering project.

## What It Does

- Fetches OHLCV price data, fundamentals (P/E, market cap, revenue, earnings), and industry peers via `yfinance`
- Computes technical indicators deterministically using `pandas-ta`: SMA 50/150/200, MACD, 52-week high/low, Minervini Trend Template, and VCP pattern detection
- Searches the web for recent news, risk flags, and lawsuits using DuckDuckGo
- Scores stocks on fundamental and technical axes using a configurable `ScoringStrategy` (dynamic metric weights)
- Generates a fully structured `StockReport` via a cloud LLM (OpenAI / Gemini) using PydanticAI
- Uses a local Ollama model (`llama3.2`) for high-volume NLP tasks (news summarization, risk extraction) to minimize cloud API costs
- Exposes analysis tools via an MCP server for integration with Claude and other MCP-compatible clients
- Persists reports and job history to PostgreSQL via SQLAlchemy async ORM
- Offloads all heavy work to Celery background workers with real-time Redis progress updates
- Provides a web UI built entirely in Python using NiceGUI (no JS/HTML/CSS)

## Tech Stack

| Layer | Technology |
|---|---|
| Agent Core | `pydantic-ai`, `pydantic v2` |
| Cloud LLM | OpenAI / Gemini (final reasoning) |
| Local LLM | Ollama `llama3.2` (NLP tasks) |
| Market Data | `yfinance`, `pandas-ta` |
| Web Search | `duckduckgo-search` |
| API Layer | `FastAPI` |
| Frontend | `NiceGUI` (Python-only, no JS) |
| Task Queue | `Celery` + `Redis` |
| Database | `PostgreSQL` + `SQLAlchemy` async + `Alembic` |
| MCP Server | Custom MCP server exposing agent tools |
| Observability | `Logfire` |
| DevOps | Docker (multi-stage), Docker Compose (5-service stack), GitHub Actions CI/CD |

## Architecture Overview

The system follows a strict separation between data pipelines and LLM reasoning:

1. **Fundamental Pipeline** — fetches financials and news, extracts risk flags
2. **Technical Pipeline** — computes indicators from OHLCV data, runs trend/pattern detection
3. **Scoring Layer** — produces a weighted composite score using a configurable strategy
4. **Agent Layer** — PydanticAI agent receives pre-scored data and generates the final `StockReport`
5. **Worker Layer** — all pipeline work runs in Celery tasks; progress streamed to Redis
6. **UI Layer** — NiceGUI web app polls job status and renders reports in real time

## Project Status

This project is being built step-by-step following a **62-step Atomic Commit Protocol**. Each step corresponds to one logical unit of functionality with a defined commit message.

- **Completed:** Steps 1–27
- **Current:** Step 28 — Interactive CLI for ticker input and weight configuration
- **Remaining:** Steps 28–62 (worker layer, UI, database, Docker, CI/CD)

## Running Locally

```bash
uv sync                          # install dependencies
cp .env.example .env             # configure environment variables
uv run python -m stock_agent.main  # run CLI
uv run python -m stock_agent.ui.app  # run web UI
```

For the full stack (app + worker + Redis + PostgreSQL + Ollama):

```bash
docker-compose up --build
```

## License

MIT
