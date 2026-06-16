# Demo Transcript

This transcript uses deterministic mock data. It is intended to show the typed
output shape, not current market values.

```bash
uv run stock-agent --ticker NVDA --mock
```

```json
{
  "ticker": "NVDA",
  "company_name": "NVIDIA Corporation",
  "current_price": 123.45,
  "analysis_date": "2026-06-16T12:00:00Z",
  "market_summary": "NVIDIA Corporation is shown in mock mode with strong growth context, constructive technical posture, and valuation risk kept visible.",
  "fundamental_score": 7.4,
  "technical_score": 8.2,
  "weighted_score": 7.8,
  "calculation": "(7.4 x 0.50) + (8.2 x 0.50) = 7.8",
  "key_points": [
    {
      "text": "Revenue growth sample of 42% supports the fundamental score",
      "sentiment": "positive"
    },
    {
      "text": "Price remains above the 50/150/200-day moving averages",
      "sentiment": "positive"
    },
    {
      "text": "Mock P/E ratio of 31.6 keeps valuation risk in view",
      "sentiment": "negative"
    },
    {
      "text": "VCP pattern is marked as detected in sample technical data",
      "sentiment": "positive"
    }
  ],
  "risks": [
    "Valuation could compress if growth expectations cool.",
    "Supply or demand shocks can affect near-term margins."
  ],
  "sources": [
    "mock://market-data/nvda",
    "mock://news-context/nvda"
  ],
  "confidence": "medium",
  "recommendation": "BUY",
  "peers": [
    {
      "ticker": "AMD",
      "weighted_score": 6.9,
      "recommendation": "WATCH"
    },
    {
      "ticker": "MSFT",
      "weighted_score": 7.1,
      "recommendation": "BUY"
    }
  ]
}
```

```text
Summary
NVDA (NVIDIA Corporation) - BUY
Weighted score: 7.8 | Confidence: medium
NVIDIA Corporation is shown in mock mode with strong growth context, constructive technical posture, and valuation risk kept visible.
```
