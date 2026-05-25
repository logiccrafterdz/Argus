---
name: strategy-ict-killzone
description: >
  Tracks the ICT_Killzone_Macro strategy — was the top performer (+$4,900) in
  the first run but has since deteriorated. Use when investigating why a
  previously profitable strategy turned unprofitable.
---

# ICT_Killzone_Macro Strategy

## Current State (Run 4 — May 2026)

| Metric | Run 1 | Run 4 |
|--------|-------|-------|
| Net Profit | +$4,900 | -$1,815 |
| Trades | 24 | 24 |
| Win Rate | 54.2% | 54.2% |
| Profit Factor | 1.89 | 0.54 |

## Analysis

This strategy went from +$4,900 to -$1,815 despite NO changes to its code.

**Root cause**: Portfolio interaction effect. When other strategies lost money faster (after their parameter changes), the bankruptcy was triggered earlier, reducing the total capital available. This changed the sizing and timing of ICT_Killzone trades.

This is strong evidence that:
1. Individual strategy P&L is misleading due to portfolio effects
2. Only portfolio-level metrics matter
3. A strategy that works in isolation may fail in a portfolio context

## Lessons Learned

1. Do not judge individual strategies in isolation — portfolio interaction distorts results
2. The circuit breaker and bankruptcy logic creates non-linear effects between strategies
3. A defensive portfolio structure (preserve capital) matters more than individual strategy performance
