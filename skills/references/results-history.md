# Backtest Results History

## Run 1 — Baseline (no modifications)

**Date**: 2026-05-24
**Commit**: `8682848` (initial working backtest)
**Config**: Original parameters, no strategy modifications.

| Metric | Value |
|--------|-------|
| Total Return | -50.0% |
| Net Profit | -$49,998.55 |
| Total Trades | 505 |
| Win Rate | 62.3% |
| Profit Factor | 0.46 |
| Max DD | -51.1% |
| Max DD Duration | 868 days |
| Sharpe | -3.11 |
| Expectancy | -$99.10 |

**Notes**:
- Account bankrupt by May 2022, no trades after that
- Only 3 profitable strategies: ICT_Killzone_Macro (+$4,899), ORB_Hybrid (+$313), Hidden_Divergence (+$539)
- All other 17 strategies lost money

---

## Run 2 — First Batch of Modifications

**Date**: 2026-05-25 (morning)
**Commit**: `da4b01e`
**Changes**: 5 strategies modified (see parameter-tuning-log.md)

| Metric | Value | vs Baseline |
|--------|-------|-------------|
| Total Return | -50.5% | -0.5% |
| Net Profit | -$50,525.36 | -$527 |
| Total Trades | 512 | +7 |
| Win Rate | 62.4% | +0.1% |
| Profit Factor | 0.46 | 0.00 |
| Max DD | -51.1% | 0.0% |
| Sharpe | -3.11 | 0.00 |
| Expectancy | -$98.77 | +$0.33 |

**Notes**:
- Results essentially unchanged despite 5 strategy modifications
- Hidden_Divergence dropped from +$539 to -$693 (portfolio interaction effect — wasn't modified)
- ADX_TrendStrength went from 0 trades to 3 trades (-$921)

---

## Run 3 — Full ATR-based SL/TP for All Strategies

**Date**: 2026-05-25 (midday)
**Commit**: `f17ed6d` through `6d7c5c1`
**Changes**: 12 strategies modified to use ATR-based SL/TP

| Metric | Value | vs Run 2 |
|--------|-------|----------|
| Net Profit | -$50,054.59 | +$471 |
| Total Trades | 510 | -2 |
| Win Rate | 62.3% | -0.1% |
| Profit Factor | 0.46 | 0.00 |
| Max DD | -51.1% | 0.0% |

**Notes**:
- Minor +$471 improvement (less than 1% change)
- Several strategies got worse and had to be reverted
- Bollinger_MR stopped trading entirely with new SL/TP
- Smart_Swing_Bias P&L dropped sharply

---

## Run 4 — Fixes for Regressed Strategies

**Date**: 2026-05-25 (afternoon)
**Commit**: `2bf30a0`, `0a47a15`
**Changes**: 6 strategies re-tuned (widened SL/TP, adjusted lookbacks, entry buffers)

| Metric | Value | vs Run 3 |
|--------|-------|----------|
| Net Profit | -$50,701.38 | -$647 |
| Total Trades | 509 | -1 |
| Win Rate | 62.48% | +0.2% |
| Profit Factor | 0.46 | 0.00 |
| Max DD | -51.1% | 0.0% |

**Notes**:
- Results virtually identical to Run 1 baseline
- Strategy parameter tuning has reached diminishing returns
- Decision to switch to skill-based learning loop and portfolio-level risk management

---

## Run 5 — TBD (after circuit breaker + dynamic sizing)

**Date**: TBD
**Commit**: TBD
**Changes**: Portfolio-level circuit breaker, dynamic position sizing, market regime filter

| Metric | Value | vs Run 4 |
|--------|-------|----------|
| TBD | TBD | TBD |
