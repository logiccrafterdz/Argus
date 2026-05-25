---
name: strategy-zero-trade
description: >
  Tracks the two strategies that consistently produce ZERO trades:
  SR_Breakout_Retest and Donchian_Breakout. Use when investigating why
  strategies fail to generate signals and how to fix them.
---

# Zero-Trade Strategies

## Current State (Run 4 — May 2026)

### SR_Breakout_Retest
| Metric | Run 1 | Run 2 | Run 4 |
|--------|-------|-------|-------|
| Trades | 0 | 0 | 0 |
| Signal Logic | lookback=40 | lookback=5, buffer=1.0×ATR | lookback=10, buffer=0.3×ATR |

### Donchian_Breakout
| Metric | Run 1 | Run 2 | Run 4 |
|--------|-------|-------|-------|
| Trades | 0 | 0 | 0 |
| Signal Logic | period=20, EMA=50 | period=10, EMA=20 | period=5, EMA=10, ATR SL/TP |

## Analysis

After 3 rounds of changes, these two strategies STILL produce 0 trades each.
This suggests a fundamental code issue rather than a parameter issue.

### Possible Root Causes (Not Yet Investigated)

1. **SR_Breakout_Retest**:
   - The breakout condition `close2 > recent_high` requires price to close above the lookback high on the PREVIOUS candle
   - Then the retest condition `close1 <= recent_high + buffer` requires the CURRENT candle to pull back
   - This is a very specific 2-candle pattern that may never trigger in H4 data
   - **Fix**: Change to a single-candle breakout (price TRADES above high, not closes above)

2. **Donchian_Breakout**:
   - Uses `close2 > dc_upper2` and `close1 > dc_upper1` — needs 2 consecutive closes above Donchian
   - Combined with EMA filter, this is extremely restrictive
   - **Fix**: Relax to single-bar breakout, or remove the EMA filter

## Action Required

These strategies need code-level fixes, not parameter changes:

- **SR_Breakout_Retest**: Rewrite signal logic to trigger on price touching (not closing above) the lookback high/low
- **Donchian_Breakout**: Use close price (not previous bar close) for breakout detection, or remove EMA direction requirement
