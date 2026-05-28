---
name: strategy-hidden-divergence
description: >
  Tracks the Hidden_Divergence strategy — consistently profitable across
  all runs. Use when analyzing divergence-based entries or risk allocation.
---

# Hidden_Divergence Strategy

## Current State (V2.0 — May 2026)

| Metric | Value |
|--------|-------|
| Net Profit | +$4,578 |
| Trades | 93 |
| Win Rate | 31.18% |
| Profit Factor | 1.31 |
| Composite Score | 67.4/100 (B) |

Rank: #4 of 7 in portfolio. Positive PF across 5 consecutive runs.

## What Makes It Work

1. **Consistent positive expectancy** — PF > 1.0 in all runs (except Run 2 portfolio interaction)
2. **Moderate trade frequency (93)** — More signals than before (27 in Run 1-4) while maintaining profitability
3. **Low correlation with other strategies** — Diversification benefit
4. **ATR-based risk** — Scales well across symbols

## Risks

- Win rate dropped from 81.5% (Run 1-4) to 31.18% (V2.0) despite PF improving. This is due to wider ATR-based TP capturing bigger wins but fewer of them.
- If win rate drops below 25%, investigate signal quality

## Improvement Ideas (Not Yet Attempted)

- Trend filter to avoid counter-trend divergence trades
- Test with 1.5x current ATR SL to see if win rate stabilizes
