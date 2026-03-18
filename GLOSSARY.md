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

### `ffill().bfill()` chain
The standard NaN-cleaning pattern used before passing a DataFrame to any indicator module. `ffill()` fills forward (handles middle/end gaps), `bfill()` fills backward (handles start gaps). Together guarantee zero NaN values.
