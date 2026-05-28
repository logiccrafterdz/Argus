---
name: strategy-trend-pullback
description: >
  Historical reference for the TrendPullback strategy — removed from active
  portfolio in V2.0. Retained as a template for what works in trend following.
---

# TrendPullback Strategy (INACTIVE)

## Status: Removed from Portfolio (V2.0)

TrendPullback was part of the original 20-strategy set but was removed when the
portfolio was trimmed to 7 strategies. It was profitable individually but didn't
survive cross-validation with the final 7.

## Historical Performance (Run 4 — May 2026)

| Metric | Value |
|--------|-------|
| Net Profit | +$308.43 |
| Trades | 16 |
| Win Rate | 81.25% |
| Profit Factor | 1.32 |

## What Made It Work

1. **Selective entry**: Only 16 trades over 3 years
2. **High win rate**: 81.25%
3. **EMA structure**: Uses 50/200 EMA for trend direction
4. **Market structure confirmation**: Pullback to structure level

## Key Parameters (for reference)

- fast_ema_period = 50
- slow_ema_period = 200
- market_structure_period = 30
- tp_multiplier = 2.0

## Lessons Retained

1. Low frequency + high WR can be profitable but hard to scale
2. EMA 50/200 is a simple but effective regime filter
3. Market structure adds edge to pure trend-following
