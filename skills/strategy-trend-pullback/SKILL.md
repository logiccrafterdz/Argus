---
name: strategy-trend-pullback
description: >
  Tracks the TrendPullback strategy — one of only two profitable strategies.
  Use as a template for what works in this portfolio and when considering
  changes to trend-following strategies.
---

# TrendPullback Strategy

## Current State (Run 4 — May 2026)

| Metric | Value |
|--------|-------|
| Net Profit | +$308.43 |
| Trades | 16 |
| Win Rate | 81.25% |
| Profit Factor | 1.32 |

## What Makes It Work

1. **Selective entry**: Only 16 trades — waits for pullbacks in strong trends
2. **High win rate**: 81.25% — trades with the trend, not against it
3. **EMA structure**: Uses 50/200 EMA to identify trend direction
4. **Market structure confirmation**: Requires pullback to structure level

## Key Parameters

```python
class TrendPullback:
    fast_ema_period = 50
    slow_ema_period = 200
    market_structure_period = 30
    tp_multiplier = 2.0  # R:R ratio
```

## Lessons for Other Strategies

1. **Low frequency + high win rate** beats high frequency + low win rate in this portfolio
2. **Trend following with structure** works better than pure breakout strategies
3. **EMA trend filter** (50/200) is a simple but effective regime filter

## Improvement Ideas (Not Yet Attempted)

1. Increase TP to 3.0× ATR to capture larger moves
2. Add partial close at 1.5R (like the engine's default)
3. Add trailing stop after 2R profit
