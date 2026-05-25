---
name: strategy-avwap-confluence
description: >
  Tracks the AVWAP_Confluence strategy — the biggest single loser in the
  portfolio (-$9,694). Use when analyzing the worst-performing strategies
  to understand what not to do.
---

# AVWAP_Confluence Strategy

## Current State (Run 4 — May 2026)

| Metric | Value |
|--------|-------|
| Net Profit | -$9,694.58 |
| Trades | 64 |
| Win Rate | 59.4% |
| Profit Factor | 0.42 |

## Analysis

AVWAP_Confluence is the single biggest loser in the portfolio, responsible for
~19% of total losses. It has the highest trade count (64), suggesting it
overtrades in unfavorable conditions.

**Key issues**:
1. **High trade frequency** — takes too many low-quality setups
2. **Poor loss management** — average loss far exceeds average win
3. **VWAP reversion in trending markets** — fading strong trends is deadly

## Improvement Ideas (Not Yet Attempted)

1. **Reduce trade frequency**: Add additional confluence filters (e.g., require price > EMA50 for long, < EMA50 for short)
2. **Widen SL**: Current 1.0× ATR SL may be too tight for VWAP-based entries
3. **Add regime filter**: Disable during strong trends (ADX > 30) since VWAP reversion fails in strong trends
4. **Reduce allocation**: Cap at 50% of original position size

## Experimentation Priority

This strategy should be the FIRST target for improvement given its outsized loss contribution.
