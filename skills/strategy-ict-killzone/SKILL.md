---
name: strategy-ict-killzone
description: >
  Tracks the ICT_Killzone_Macro strategy — improved to PF 1.300 but not in
  active portfolio. Use as a reference for killzone-based experiments.
---

# ICT_Killzone_Macro Strategy

## Status: NOT in Active Portfolio

Improved individually to PF 1.300 (+11.60%, DD -4.85%) but removed from
portfolio because adding it worsened overall results (PF 1.17 to 0.98).

## Improvement Experiment (May 2026, commit 7584207)

| Metric | Before (Run 4) | After (Single) |
|--------|----------------|----------------|
| Net Profit | -$1,815 | +$1,218 (11.60%) |
| Profit Factor | 0.54 | 1.300 |
| Max DD | — | -4.85% |

**Changes made**:
1. Killzone shifted from 8-11 UTC (multi-session) to pure London (7-9 UTC)
2. TP increased to 16 ATR (was 2.0x)

## Why It Failed Portfolio Integration

Despite excellent single-strategy results, adding ICT_Killzone to the 7-strategy
portfolio caused PF to drop from 1.17 to 0.98. The strategy likely overlaps with
existing session-based entries (London open moves already captured).

**Lesson**: A strategy that works in isolation may still hurt the portfolio.
