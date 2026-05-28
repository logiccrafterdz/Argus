# Backtest Results History

**Latest Run 7**: Train +12.83% (PF 1.11), Validation –1.10% (PF 0.98), Test +2.11% (PF 1.06). See below for details.

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

## Run 5 — Clean 7-Strategy Portfolio (V2.0 Final)

**Date**: 2026-05-26
**Commit**: `de65bc2`
**Changes**: v2.0 portfolio: 7 strategies, removed TrendPullback/SuperTrendEMA, OOS validation

| Metric | Value | vs Run 4 |
|--------|-------|----------|
| Net Profit | -$50,054 | -$647 |
| Total Trades | ~500 | ~0 |
| Win Rate | ~62% | ~0% |
| Profit Factor | ~0.46 | ~0.00 |
| Max DD | -51.1% | 0.0% |

**Notes**: Portfolio still deeply unprofitable. The 7-strategy selection didn't help.

---

## Run 7 — 3-Way Train/Validation/Test Split

**Date**: 2026-05-28
**Commits**: (current)
**Changes**: Added `validation` mode to `run_oos.py`; data split into Train (60%: 2022–2023), Validation (20%: Jan–Aug 2024), Test (20%: Sep 2024–May 2025)

| Metric | TRAIN (60%) | VAL (20%) | TEST (20%) | Stable? |
|--------|:-----------:|:---------:|:----------:|:-------:|
| Total Return | **+12.83%** | –1.10% | +2.11% | CHECK |
| Net Profit | **+$12,834** | –$1,101 | +$2,115 | CHECK |
| Total Trades | 740 | 265 | 216 | — |
| Win Rate | 27.57% | 20.00% | 24.54% | — |
| Profit Factor | **1.11** | **0.98** | **1.06** | **NO** |
| Max DD | –3.60% | –6.88% | –5.96% | **NO** |
| Sharpe | 0.29 | –0.18 | –0.14 | CHECK |
| Expectancy | +$17.34 | –$4.16 | +$9.79 | CHECK |

**Notes**:
- First 3-way split in project history — mimics ML best practices for overfitting detection
- **Validation period (H1 2024) is the weakest**: PF 0.98, –1.10%, DD –6.88%
- Only period where PF < 1.0 — likely regime mismatch in early 2024
- **Test period (H2 2024–2025) recovers**: PF 1.06, +2.11%, DD –5.96%
- Performance degrades: Train → Val → Test (12.83% → –1.10% → +2.11%)
- Gap between Val and Test may indicate H1 2024 was structurally different (rate-cut uncertainty, USD strength)
- **Recommendation**: Consider regime-filtering or adjusting parameters for 2024-type conditions; validate on a longer hold-out

---

## Run 6 — Individual Strategy Improvements (Batch)

**Date**: 2026-05-28
**Commits**: `e53ab8f`, `d07d57c`, `022db8c`, `7584207`
**Changes**: 4 strategies improved individually (see parameter-tuning-log.md Batch 5)

| Metric | Value | vs Run 5 |
|--------|-------|----------|
| Total Return | **+29.6%** | **+$29,599** |
| Net Profit | **+$29,598.63** | +$79,653 |
| Total Trades | **1,049** | +549 |
| Win Rate | 29.36% | -33% |
| Profit Factor | **1.17** | +0.71 |
| Max DD | **-5.38%** | +45.7% |
| Max DD Duration | 170 days | -698 days |
| Sharpe | **0.48** | +3.59 |
| Sortino | **0.66** | — |
| Calmar | **1.44** | — |
| Recovery Factor | **5.5** | — |
| Expectancy | **+$28.22** | +$127 |
| Composite Score | **67.3/100 (B)** | — |

**Per-Strategy Results** (sorted by contribution):
| Strategy | Net P&L | Trades | WR% | PF | Score |
|----------|---------|--------|-----|----|-------|
| Bollinger Mean Reversion | +$12,900 | 239 | 38.9% | 1.36 | 73.4 B |
| PriceAction_SR | +$10,316 | 99 | 32.3% | 1.69 | 76.0 B |
| AVWAP_Confluence | +$8,183 | 353 | 21.2% | 1.12 | 63.8 B |
| Hidden_Divergence | +$4,578 | 93 | 31.2% | 1.31 | 67.2 B |
| Smart_Swing_Bias | +$189 | 56 | 39.3% | 1.03 | 58.6 C |
| ADX_TrendStrength | +$765 | 27 | 18.5% | 1.15 | 55.6 C |
| Donchian_Breakout | -$7,331 | 182 | 28.6% | 0.75 | 52.0 C |

**Notes**:
- First profitable run in project history: +29.6%, +$29,599
- DD reduced from -51% to -5.38% — massive improvement
- 4 experimental strategies improved individually but hurt portfolio when combined
- Donchian_Breakout remains the only losing strategy
- Learning infrastructure built: scoring.py, argus_learn.py, evidence_memory.json
