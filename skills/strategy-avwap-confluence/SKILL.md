---
name: strategy-avwap-confluence
description: >
  Tracks the AVWAP_Confluence strategy — now one of the TOP performers in the
  portfolio. Use when evaluating strategy strengths or considering AVWAP changes.
---

# AVWAP_Confluence Strategy

## Current State (V2.0 — May 2026)

| Metric | Value |
|--------|-------|
| Net Profit | +$8,182.68 |
| Trades | 353 |
| Win Rate | 21.25% |
| Profit Factor | 1.12 |
| Composite Score | 63.8/100 (B) |
| Contribution | 27.6% of portfolio profit |

## Analysis

AVWAP_Confluence is now the **third-largest profit contributor**, behind Bollinger Mean Reversion and PriceAction_SR. Despite a low win rate (21%), the strategy's average win significantly exceeds its average loss, producing a solid PF of 1.12.

**Key characteristics**:
1. **High trade frequency** — 353 trades across 3 years (most active strategy)
2. **Low win rate, high R:R** — wins are ~3x larger than losses on average
3. **Diversification benefit** — low correlation with other strategies

## What Works
- Current ATR-based SL at 1.0x works well with the high-frequency approach
- The strategy captures large VWAP deviations effectively
- Good diversification from mean-reversion strategies

## What We Know (from prior runs)
- Was the biggest loser (-$9,695) in Run 4 under old parameters
- ATR-based SL/TP + appropriate buffer transformed it from worst to best
- Key insight: VWAP strategies need wider SL than other strategies to succeed

## Monitoring
- If win rate drops below 15%, or PF drops below 1.0, investigate
- If monthly return variance exceeds +-4%, check for regime change
- Consider reducing allocation if correlation with Hidden_Divergence exceeds 0.6
