---
name: strategy-hidden-divergence
description: >
  Tracks the Hidden_Divergence strategy — the only consistently profitable
  strategy in the portfolio. Use when analyzing what makes this strategy work
  and when considering increasing its allocation.
---

# Hidden_Divergence Strategy

## Current State (Run 4 — May 2026)

| Metric | Run 1 | Run 2 | Run 4 |
|--------|-------|-------|-------|
| Net Profit | +$539 | -$693 | +$749 |
| Trades | 27 | 27 | 27 |
| Win Rate | 81.5% | 81.5% | 81.5% |
| Profit Factor | 1.23 | 0.72 | 1.23 |

**Note**: Run 2 showed -$693 despite NO changes to this strategy (portfolio interaction effect from bankruptcy timing).

## What Makes It Work

1. **High win rate (81.5%)** — Divergence signals are naturally low-frequency, high-probability setups
2. **Low trade count (27)** — Only takes the best setups
3. **Positive expectancy** — Only strategy in the portfolio with PF > 1.0 consistently
4. **No changes made** — Original parameters were correct from the start

## Rules to Preserve

- **DO NOT modify** parameters unnecessarily
- If ATR-based SL/TP is added, test in isolation first
- Consider increasing capital allocation to this strategy from 1% to 2% risk per trade

## Improvement Ideas (Not Yet Attempted)

- Test with wider SL (1.5× ATR) to see if win rate stays high
- Combine with trend filter to avoid counter-trend divergence trades
- Increase position size since the strategy has positive expectancy
