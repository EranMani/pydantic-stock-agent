# Project Glossary

Quick reference for financial concepts, pandas functions, async/Python terms, and project-specific vocabulary used throughout this codebase.

---

## Pandas Functions

### `pd.DataFrame()`
Creates a two-dimensional tabular data structure with labeled rows and columns. Used throughout the project to represent OHLCV price data.
```python
df = pd.DataFrame({"Close": [100.0, 102.0], "Volume": [1_000_000, 1_200_000]})
```

### `df.loc[row, column]`
Label-based indexing — selects rows and columns by their label or index value. Used to read or write specific cells.
```python
df.loc[100:105, "Close"] = np.nan   # set rows 100-105 of Close column to NaN
df.loc[0, "Close"]                  # read the Close value at row 0
```

### `df.iloc[row, column]`
Integer-position based indexing — selects by position (0, 1, 2...) rather than label. Used when you need the Nth row regardless of its label.
```python
df.iloc[-1]        # last row
df.iloc[0, 3]      # first row, fourth column
```

### `df.ffill()`
Forward fill — propagates the last known non-NaN value forward to fill subsequent NaN gaps. Does not fill NaN at the very start (nothing to carry forward).
```python
# Before: [100.0, NaN, NaN, 102.0]
# After:  [100.0, 100.0, 100.0, 102.0]
df.ffill()
```

### `df.bfill()`
Backward fill — propagates the next known non-NaN value backward. Used after `ffill()` to handle NaN at the start of the DataFrame.
```python
# Before: [NaN, NaN, 100.0, 102.0]
# After:  [100.0, 100.0, 100.0, 102.0]
df.bfill()
```

### `df.isna()`
Returns a boolean DataFrame of the same shape — `True` where values are NaN, `False` elsewhere. Used for validation checks.
```python
df.isna().sum()          # count NaN per column
df.isna().sum().sum()    # total NaN count across entire DataFrame
```

### `df.drop(columns=[])`
Removes specified columns from the DataFrame. Returns a new DataFrame — does not modify in place by default.
```python
df = df.drop(columns=["Dividends", "Stock Splits"])
```

### `df.tail(n)`
Returns the last `n` rows of the DataFrame. Used to inspect the most recent data.
```python
df.tail(1)    # most recent trading day
df.tail(3)    # last 3 trading days
```

### `df.head(n)`
Returns the first `n` rows of the DataFrame.
```python
df.head(5)    # first 5 rows
```

### `df.shape`
Returns a tuple `(rows, columns)` representing the dimensions of the DataFrame.
```python
df.shape       # e.g. (501, 7)
df.shape[0]    # number of rows
```

---

## NumPy

### `np.nan`
The standard floating-point representation of a missing value. Pandas recognises `np.nan` and handles it in functions like `ffill()`, `bfill()`, `isna()`.
```python
import numpy as np
np.nan          # used to inject missing values in tests
```

---

## Financial Concepts

### OHLCV
**Open, High, Low, Close, Volume** — the five standard fields in a daily price bar:
- **Open** — price at market open
- **High** — highest price during the session
- **Low** — lowest price during the session
- **Close** — price at market close (adjusted for splits/dividends)
- **Volume** — number of shares traded during the session

### P/E Ratio (Price-to-Earnings)
The ratio of a stock's price to its earnings per share. A lower P/E generally indicates better value. Can be negative for loss-making companies. `None` when the company has no earnings.
```
P/E = Stock Price / Earnings Per Share
```

### Beta
Measures a stock's price sensitivity relative to the market:
- `beta = 1.0` → moves 1:1 with the market
- `beta = 2.0` → moves 2x the market (amplified in both directions)
- `beta = -1.0` → moves inversely to the market (e.g. gold ETFs)
- `beta = 0.5` → half the market's volatility

### Revenue Growth
Year-over-year percentage change in a company's revenue. Expressed as a decimal (e.g. `0.59` = 59% growth). Can be negative during revenue contraction.

### Market Cap
Total market capitalisation — the total value of all outstanding shares:
```
Market Cap = Share Price × Total Shares Outstanding
```
Always non-negative. Used as a stability signal — larger caps are generally more stable.

### SMA (Simple Moving Average)
The arithmetic mean of closing prices over a specified number of days. Used to identify trend direction.
- **SMA_50** — 50-day average (short-term trend)
- **SMA_150** — 150-day average (medium-term trend)
- **SMA_200** — 200-day average (long-term trend). Requires at least 200 bars of history.

### MACD (Moving Average Convergence Divergence)
A momentum indicator derived from two exponential moving averages (12-day and 26-day). Produces three values:
- **MACD line** — difference between 12-day and 26-day EMA
- **Signal line** — 9-day EMA of the MACD line
- **Histogram** — difference between MACD line and signal line

### 52-Week High / Low
The highest and lowest closing prices over the past 52 weeks (252 trading days). Used in the Minervini Trend Template.

### Minervini Trend Template
A set of conditions defined by trader Mark Minervini to identify stocks in a strong uptrend:
1. Price above SMA_150 and SMA_200
2. SMA_200 trending upward for at least 1 month
3. SMA_50 above SMA_150 and SMA_200
4. Price within 25% of its 52-week high
5. Price at least 30% above its 52-week low

### VCP (Volatility Contraction Pattern)
A chart pattern also defined by Minervini. Characterised by successive price ranges narrowing over time — each contraction is smaller than the previous. Signals a stock coiling before a potential breakout.

### Weighted Score
The final combined score produced by merging the fundamental and technical scores using `ScoringStrategy` weights:
```
weighted_score = (fundamental_score × fundamental_weight)
              + (technical_score  × technical_weight)
```

---

## Async & Python Concepts

### Event Loop
The single-threaded scheduler at the heart of Python's `asyncio`. Manages and switches between coroutines at `await` points. A blocking call inside an async function freezes the entire event loop — nothing else can run.

### Coroutine (`async def`)
A function defined with `async def` that can be paused and resumed at `await` points. Must be awaited or run with `asyncio.run()`.

### `asyncio.to_thread(fn, *args)`
Runs a synchronous blocking function in a thread pool worker, freeing the event loop to handle other work while waiting. Used for all yfinance and DuckDuckGo calls.
```python
result = await asyncio.to_thread(blocking_function, arg1, arg2)
```

### `asyncio.gather(*coroutines)`
Runs multiple coroutines concurrently and waits for all of them to complete. Returns a list of results in the same order as the input coroutines.
```python
results = await asyncio.gather(fetch_a(), fetch_b(), fetch_c())
```

### `asyncio.run(coroutine)`
The sync-to-async bridge. Runs a coroutine from synchronous code by creating a new event loop. Used in Celery task bodies to delegate to `_async_*` functions.
```python
result = asyncio.run(my_async_function())
```

---

## Project-Specific Terms

### `ScoringStrategy`
A Pydantic model that configures which metrics are active and how to weight them. Passed via dependency injection into every agent tool. Controls dynamic routing in the scoring pipeline.

### `AgentDependencies`
A Python `@dataclass` that acts as the dependency injection container for PydanticAI. Carries the `ScoringStrategy` into every `@agent.tool` via `ctx.deps`.

### Sub-score
A normalised float in `[0.0, 1.0]` representing how good a single metric's value is. Computed before weighting. Independent of the metric's weight.

### Re-normalisation
The process of re-scaling active metric weights so they always sum to `1.0`, regardless of how many metrics are active in the strategy. Prevents excluded metrics from artificially shrinking the score range.

### Context Window
The maximum amount of text (tokens) an LLM can process in a single call. Everything passed to the model — system prompt, tool results, conversation history — consumes tokens. Keeping the context window lean and signal-rich improves reasoning quality and reduces cost.

### Context Engineering
The practice of deterministically filtering, deduplicating, and structuring data before it reaches the LLM — so the model's context window contains only high-signal, relevant information. The opposite of dumping raw data into the prompt.

### RISK_KEYWORDS
A module-level constant list of strings used by `extract_risk_flags()` to filter news snippets. Only snippets containing at least one keyword pass through to the LLM context.

### `@agent.tool`
PydanticAI decorator that registers an `async def` function as a callable tool on an agent. At decoration time it builds a JSON schema from the function's parameters and adds it to the agent's toolset. `RunContext[T]` parameters are injected by the framework — the LLM never sees them.

### `RunContext[T]`
The dependency injection context passed as the first parameter to every `@agent.tool` function. `ctx.deps` contains the `AgentDependencies` instance configured for the current run. `T` is the deps type (e.g. `RunContext[AgentDependencies]`).

### `TestModel`
A PydanticAI model (`pydantic_ai.models.test.TestModel`) that never makes HTTP calls. Used in tests to verify agent wiring, schema validation, and dependency injection without a real API key. Key options: `call_tools=[]` (skip tool calls), `custom_output_args` (provide a valid output dict).

### Lazy Initialisation / Lazy Import
A pattern where an object is not created (or a module is not imported) until the first time it is actually needed — at **call time**, not at **module load time**.

**Form 1 — lazy initialisation via `@lru_cache`:**
Used when an object is expensive to construct or depends on external resources that may be unavailable at startup. In this project, `get_ollama_agent()` defers Ollama agent construction until first use — the module imports cleanly even when Ollama is offline.
```python
@lru_cache(maxsize=1)
def get_ollama_agent() -> Agent:
    return Agent(ollama_model)  # only runs on first call, result cached forever
```

**Form 2 — lazy import inside a function body:**
Used to break circular imports — when two modules need each other but neither can be fully loaded first. Moving the import inside the function body defers it to call time, by which point both modules are fully loaded.
```python
# fundamental_tools.py — loaded by agent.py BEFORE run_analysis is defined
@agent.tool
async def get_peer_reports(ctx, ticker):
    from stock_agent.agent import run_analysis  # safe: agent.py is fully loaded by call time
    peers = await fetch_industry_peers(ticker)
    results = await asyncio.gather(*[run_analysis(p, ctx.deps.strategy) for p in peers[:5]])
    return [PeerReport(...) for r in results]
```

**Why not just reorder the imports?** In this project, `agent.py` must import `fundamental_tools.py` to trigger `@agent.tool` registration, and `fundamental_tools.py` must import `agent` to access the `agent` object for `@agent.tool`. This is a genuine circular dependency — lazy import is the correct resolution, not a workaround.

### Heavy Tool vs Lightweight Tool
A distinction in agentic tool design. **Heavy tools** (e.g. `get_technical_data`) run the full pipeline — expensive, called once. **Lightweight tools** (e.g. `get_moving_average_signal`) return a specific subset of data cheaply — called on demand when the LLM needs to verify a detail without re-running the full pipeline.

### OpenAI-Compatible API
An API that implements the same endpoint contract as OpenAI's `/v1/chat/completions`. Allows non-OpenAI models (e.g. Ollama, LM Studio) to be used with OpenAI client libraries or pydantic-ai's `OpenAIModel`. Ollama exposes this at `{OLLAMA_HOST}/v1`.

### Closure Variable Capture in Loops
A common Python gotcha: when a `lambda` or `def` inside a loop references a loop variable, all closures end up capturing the *same* variable — its final value after the loop ends, not the value at the time the closure was created.

```python
# BUG — all checkboxes call handler with the last value of `key`
for key, label in items:
    checkbox.on_value_change(lambda e: toggle(key))  # key is captured by reference

# FIX — factory function creates a new scope per iteration
for key, label in items:
    def make_handler(k: str):        # k is a new local variable each call
        def handler(e) -> None:
            toggle(k)               # captures k, not key
        return handler
    checkbox.on_value_change(make_handler(key))
```

Used in `strategy_panel.py` for fundamental metric and technical indicator checkboxes — each checkbox must capture its own `key`, not the loop variable.

### Reactive Binding (NiceGUI)
A pattern where a UI element's value is linked directly to a Python variable. When the variable changes, the UI updates automatically — and vice versa. NiceGUI implements this via `.bind_value(obj, 'attr')` for two-way binding, or `on_value_change(callback)` for explicit change handlers.

In this project, the weight slider in `strategy_panel.py` uses `on_value_change` to update `StrategyState.fundamental_pct` whenever the slider moves — the `ScoringStrategy` always reflects the current UI state without any manual sync.

```python
slider.on_value_change(lambda e: setattr(state, 'fundamental_pct', int(e.value)))
```

### `ffill().bfill()` chain
The standard NaN-cleaning pattern used before passing a DataFrame to any indicator module. `ffill()` fills forward (handles middle/end gaps), `bfill()` fills backward (handles start gaps). Together guarantee zero NaN values.

---

## NiceGUI / UI Concepts

### Design Token System
A design token is a named constant that represents a single visual decision — a colour, a spacing value, a font size. Instead of hardcoding `"text-sm leading-relaxed"` in five different components, you define it once in `theme.py` as `TYPOGRAPHY["body"]` and reference the name everywhere.

In this project, design tokens are **Python dicts in `src/stock_agent/ui/theme.py`**, mapping semantic names to Tailwind utility class strings. There are no CSS custom properties (`--color-brand`) because this project has no CSS files.

The token system has six dicts:
- `COLOURS` — colour fragments (used as `f"text-{COLOURS['muted']}"`)
- `TYPOGRAPHY` — semantic type composites (`TYPOGRAPHY["section_label"]`)
- `SPACING` — gap and padding classes (`SPACING["card_padding"]`)
- `RADIUS` — border radius scale (`RADIUS["md"]`)
- `SHADOW` — elevation scale (`SHADOW["sm"]`)
- `TRANSITIONS` — motion utilities (`TRANSITIONS["normal"]`)

```python
# Without tokens — fragile, easy to drift across files
ui.label("Scores").classes("text-xs font-semibold uppercase tracking-wide text-gray-500")

# With tokens — single source of truth
from stock_agent.ui.theme import TYPOGRAPHY, COLOURS
ui.label("Scores").classes(f"{TYPOGRAPHY['section_label']} text-{COLOURS['subtle']}")
```

### `ui.expansion()` (NiceGUI)
A collapsible disclosure widget. Renders a header row that toggles the visibility of its child content. Used in `strategy_panel.py` to hide the scoring metric toggles by default, keeping the main dashboard clean.
```python
with ui.expansion("Scoring Strategy", icon="tune"):
    # content hidden until user clicks the header
    ui.label("shown when expanded")
```
Collapsed by default (no `value=True` needed). Equivalent to an HTML `<details>` element but styled with Quasar/Tailwind.

### `color=None` on `ui.button()`
NiceGUI buttons default to `color='primary'`, which activates Quasar's scoped color CSS. This overrides Tailwind `bg-*` classes at higher specificity — making `.classes("bg-indigo-600")` invisible. Setting `color=None` removes Quasar's color prop entirely, making Tailwind the sole visual authority. Required any time a button uses custom Tailwind color classes.
```python
# Wrong — Quasar overrides the bg class
ui.button("Click").classes("bg-indigo-600 text-white")

# Correct — Tailwind wins
ui.button("Click", color=None).classes("bg-indigo-600 text-white")
```

### `_classes.clear()` + `.classes()` + `.update()` pattern
The correct way to fully replace a NiceGUI element's Tailwind classes at runtime. `.classes(string, replace=True)` passes a bool to a parameter expecting a string, causing `AttributeError`. The safe pattern:
```python
btn._classes.clear()        # wipe all existing classes
btn.classes(NEW_CLASSES)    # apply the full new class string
btn.update()                # push the change to the browser
```
Used in pill toggle handlers to swap between `PILL_ACTIVE` and `PILL_INACTIVE` tokens.

### Tailwind Responsive Prefixes
Tailwind's mobile-first responsive system. A class prefixed with `sm:`, `md:`, `lg:`, or `xl:` only applies at that breakpoint and above. Used in NiceGUI via `.classes()` — no CSS files needed.

```python
# Stacks vertically on mobile, side-by-side on tablet+
ui.row().classes("flex-col md:flex-row gap-4")

# Max-width scales up with screen size
ui.column().classes("w-full max-w-sm md:max-w-2xl lg:max-w-4xl mx-auto")
```
