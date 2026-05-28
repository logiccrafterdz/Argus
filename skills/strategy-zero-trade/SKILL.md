---
name: strategy-zero-trade
description: >
  Historical reference: SR_Breakout_Retest and Donchian_Breakout previously
  produced zero trades. This has been resolved in V2.0 — both now generate
  active signals. Retained as a "don't repeat" reference.
---

# Zero-Trade Strategies (Historical — RESOLVED)

## Resolution (V2.0 — May 2026)

Both strategies now produce active trades:

### SR_Breakout_Retest
- **Status**: Not in active portfolio (but generates trades independently)
- **Fix**: Candle body confirmation filter + configurable lookback/buffer
- **Key learning**: Single-candle breakout detection (close > recent_high) + retest confirmation works on H4
- **Current PF**: 1.023 (single-strategy test)

### Donchian_Breakout
- **Status**: Active in portfolio — 182 trades, PF 0.75 (needs improvement)
- **Fix**: Reduced period (5) and EMA (10), single-bar breakout logic
- **Key learning**: Needs further optimization — still the only losing strategy in portfolio

## Root Cause (Historical)
These two strategies had specific 2-candle pattern requirements that were too restrictive for H4 data. The fix was to:
1. Simplify to single-candle breakout detection
2. Add ATR-based entry buffer to avoid noise
3. Reduce lookback periods for faster signal generation

## "Don't Repeat" Record
- **Don't** use two-consecutive-close breakout conditions on H4 (too slow)
- **Don't** combine EMA filter + breakout on already-filtered strategies (double-filter kills signals)
- **Don't** set buffer to 0 on breakout strategies (noise triggers)
