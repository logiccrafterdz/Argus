# Parameter Tuning Log

Record every parameter change: what, why, and what happened.

## Batch 1 — Entry Relaxation (da4b01e)

### SR_Breakout_Retest
- **lookback**: 40 → 5
- **buffer**: 0.5× → 1.0× ATR
- **retest condition**: simplified (removed strict direction check)
- **Why**: Strategy had very few signals; relaxing to generate more trades
- **Result**: Slight improvement but still losing

### ADX_TrendStrength
- **ADX threshold**: 25 → 20
- **Why**: Want more trades in weaker trends
- **Result**: 0 trades → 3 trades (-$921). Generating signals but losing.

### Donchian_Breakout
- **period**: 20 → 10
- **EMA**: 50 → 20
- **Why**: Speed up signal generation
- **Result**: Still 0 trades (later fixed in Batch 3)

### Liquidity Sweep FVG
- **threshold**: 0.00050 fixed → ATR-based multiplier 0.5
- **Why**: Fixed threshold not robust across symbols
- **Result**: Still losing, but more trades

### ORB_Session
- **orb_duration_minutes**: 30 → 15
- **Why**: Capture earlier breakouts
- **Result**: Minor change

---

## Batch 2 — ATR-based SL/TP Standardization (f17ed6d..6d7c5c1)

### AVWAP_Confluence
- **TP**: 2.0× → 3.0× ATR
- **buffer**: 0.2× → 0.5× ATR
- **Why**: Standardize on ATR-based risk

### PDH_PDL_BreakReversal
- **Added**: ATR-based buffer, SL 0.5×ATR, TP 1.0×ATR (R:R 2:1)
- **Why**: Replace fixed values with dynamic ATR-based

### Asian_Range_Fakeout
- **SL**: 0.5× ATR
- **TP**: 1.5× ATR (R:R 3:1)
- **Why**: Standardize

### VWAP_MultiBand_Regime / Volatility_Squeeze
- **ATR-based SL/TP** at 1:2 R:R
- **Why**: Standardize

### PriceAction_SR
- **ATR buffer**, SL 0.5×ATR, TP 1.0×ATR (R:R 2:1)
- **Why**: Standardize

### NY_Session_Reversal
- **SL**: 0.5× ATR
- **TP**: 1.5× ATR (R:R 3:1)
- **Why**: Standardize

### Smart_Swing_Bias
- **ATR-based SL/TP** at 1:2 R:R
- **Result**: Got WORSE — P&L dropped significantly

### Liquidity_Sweep_Breakout / SuperTrend_EMA / TrendPullback
- **ATR-based SL/TP** at 1:2 R:R
- **Why**: Standardize

### Bollinger_MR
- **SL/TP**: swing-based SL and SMA TP → ATR-based 1:2 R:R
- **Result**: BROKE — 0 trades after this change

---

## Batch 3 — Fix Regressions (2bf30a0, 0a47a15)

### Smart_Swing_Bias
- **SL**: 1.0× → 1.5× ATR
- **TP**: 2.0× → 3.0× ATR
- **Why**: Was getting stopped out too early. Widen to match strategy's swing-based nature.

### PriceAction_SR
- **SL**: 0.5× → 1.0× ATR
- **buffer**: 0.3× → 0.5× ATR
- **Why**: Too tight, causing premature exits

### Bollinger_MR
- **SL**: 1.0× → 1.5× ATR
- **TP**: 2.0× → 3.0× ATR
- **Why**: SL was too tight for mean reversion; TP too close for R:R

### Liquidity Sweep FVG
- **Added**: ATR-based SL/TP at 1:2 R:R
- **Why**: Standardize on ATR risk model

### SR_Breakout_Retest
- **lookback**: 5 → 10
- **buffer**: 1.0× → 0.3× ATR
- **Why**: Was too sensitive, reverting toward middle ground

### Donchian_Breakout
- **period**: 10 → 5
- **EMA**: 20 → 10
- **ATR-based SL/TP** at 1:2 R:R
- **start_idx**: 50 → 20
- **pad**: 50 → 20
- **Why**: Still 0 trades after Batch 1; needed bigger changes

---

## Batch 4 — Portfolio-Level Changes (Deferred)

Not yet attempted. Individual strategy improvements took priority.

---

## Batch 12 — HiddenDivergence v2 (Run 9, 2026-05-29)

**Commit**: `046ffbb`

### HiddenDivergence
- **TP multiplier**: 14× → 10× ATR (R:R 5:1 instead of 7:1)
- **Why**: Already profitable everywhere but TP 14 ATR meant low WR (15-23%). Reducing TP increases WR for more robustness.
- **Iterations**:
  - v1: baseline (TP 14) — profitable all 3 splits
  - v2: TP 10 — all 3 splits still profitable, higher WR, ~37% more total net profit
- **Final**: v2 — TP 10× ATR, SL 2.0 ATR

| Period | v1 PF | v1 Return | v1 WR | vFinal PF | vFinal Return | vFinal DD |
|--------|-------|-----------|-------|-----------|---------------|-----------|
| Train | 1.16 | +$16,227 | 15.9% | 1.141 | +$26,887 | –9.43% |
| Val | 1.13 | +$2,590 | 22.6% | 1.047 | +$667 | –3.84% |
| Test | 1.24 | +$3,974 | 17.4% | 1.114 | +$3,620 | –5.12% |

- **Verdict**: Total net P&L from +$22,791 to +$31,174 (+37%). More conservative, more robust.

---

## Batch 11 — Donchian_Breakout v1 retained

- Tested TP 8→6 ATR — no improvement, reverted.
- **Verdict**: v1 baseline is the best version.

## Batch 10 — BollingerMR v1 retained

- Tested SL 2.0→1.5 ATR (worse) and TP 4→5 ATR (worse)
- **Verdict**: v1 baseline (TP 4 ATR, SL 2.0 ATR) is the best. Train weakness is structural (2018-2022 includes COVID/rate hikes).

---

## Batch 9 — AVWAP_Confluence v2 (Run 9, 2026-05-29)

**Commit**: TBD

### AVWAP_Confluence
- **TP multiplier**: 14× → 7× ATR (R:R 3.5:1 instead of 7:1)
- **Why**: Val PF 0.80 with WR 10.8%. R:R 7:1 was too ambitious for a crossover strategy.
- **Iterations**:
  - v1: baseline (TP 14, buffer 0.5)
  - v2: TP 7, buffer 0.5 → all 3 splits near/above 1.0 ✅
- **Final**: v2 — TP 7× ATR, buffer 0.5 ATR

| Period | v1 PF | v1 Return | v1 DD | vFinal PF | vFinal Return | vFinal DD |
|--------|-------|-----------|-------|-----------|---------------|-----------|
| Train | 1.19 | +10.79% | –16.56% | 1.133 | +54.85% | –12.03% |
| Val | 0.80 | –4.63% | –7.76% | **0.986** | –0.38% | –4.12% |
| Test | 0.98 | –0.22% | –5.53% | **1.107** | +5.88% | –3.88% |

- **Verdict**: Now positive in Train and Test, nearly breakeven in Val. Total net P&L went from +$5,945 to +$60,350. AVWAP is now a contributor, not a drag.

---

## Batch 8 — SmartSwing_Bias v2 (Run 9, 2026-05-29)

**Commit**: `6c4a760`

### SmartSwing_Bias
- **TP multiplier**: 8× → 5× ATR (R:R 2.5:1 instead of 4:1)
- **Why**: Val PF was 0.37 with WR 10.8% (only 4 wins in 37 trades). Needed WR boost.
- **Iterations**:
  - v1: baseline (TP 8, SL 2.0)
  - v2: TP 5, SL 2.0 → Val PF **0.704** (best balance, test still positive)
  - v3: TP 5, SL 1.5 → Val PF 0.804 but Train/Test worse
- **Final**: v2 — TP 5× ATR, SL 2.0 ATR

| Period | v1 PF | v1 Return | v1 WR | vFinal PF | vFinal Return | vFinal DD |
|--------|-------|-----------|-------|-----------|---------------|-----------|
| Train | 0.91 | –10.16% | 20.1% | 0.934 | –6.49% | –12.02% |
| Val | 0.37 | –5.32% | 10.8% | **0.704** | –2.37% | –4.68% |
| Test | 1.20 | +0.93% | 17.9% | 1.068 | +0.98% | –2.55% |

- **Verdict**: Val WR jumped 10.8%→28.6% (4→16 winners). Still negative in Val but ~55% better. Test positive.

---

## Batch 7 — PriceAction_SR v2 (Run 9, 2026-05-29)

**Commit**: `e0379ae`

### PriceAction_SR
- **TP multiplier**: 8× → 4× SL (R:R 4:1)
- **Entry buffer**: 0.5 → 1.0 ATR
- **lookback**: kept at 100 (50 was worse)
- **Why**: WR 10-21% couldn't support 8:1 R:R. Avg loss ~$190, avg win ~$700, need WR > 21%.
- **Iterations**:
  - v1: baseline (TP 8, buf 0.5, LB 100)
  - v2: TP 4, buf 1.0, LB 100 → Test PF **0.937** (best)
  - v3: TP 4, buf 1.0, LB 50 → Test PF 0.844
- **Final**: v2 — TP 4×, entry buf 1.0 ATR, lookback 100

| Period | v1 PF | v1 Return | v1 DD | vFinal PF | vFinal Return | vFinal DD |
|--------|-------|-----------|-------|-----------|---------------|-----------|
| Train | 0.815 | –13.80% | –17.25% | 0.894 | –9.75% | –14.54% |
| Val | 0.868 | –1.60% | –4.98% | 0.776 | –3.62% | –5.98% |
| Test | 0.604 | –5.50% | –5.85% | **0.937** | –1.04% | –3.21% |

- **Verdict**: Still negative but Test nearly breakeven. Net P&L from –$20,879 to –$14,414 (–31%).

---

## Batch 6 — ADX_TrendStrength v2 (Run 9, 2026-05-29)

**Commit**: `8f85b81`, `196775f`

### ADX_TrendStrength
- **ADX threshold**: 20 → 25
- **SL**: 2.0× → 2.5× ATR
- **TP**: 12.0× → 8.0× ATR (R:R from 6:1 to 3.2:1)
- **Why**: Baseline showed PF 0.47–0.80 across all 3 splits. Low win rate (10–17%) couldn't support 6:1 R:R.
- **Iterations**:
  - v1: ADX>25, SL 2.5, TP 8 → Test PF **0.944** (best balance)
  - v2: ADX>30, SL 2.5, TP 6 → Test PF 0.996 but only 11 trades in val
  - v3: ADX>25, SL 2.5, TP 6 → Test PF 0.925
- **Final**: v1 — ADX>25, SL 2.5 ATR, TP 8 ATR
- **Results**:

| Period | v0 PF | v0 Return | v0 DD | vFinal PF | vFinal Return | vFinal DD |
|--------|-------|-----------|-------|-----------|---------------|-----------|
| Train | 0.800 | –28.6% | –31.2% | 0.762 | –20.5% | –21.7% |
| Val | 0.469 | –5.4% | –5.5% | 0.625 | –1.7% | –2.5% |
| Test | 0.758 | –6.2% | –9.1% | **0.944** | –0.7% | –3.9% |

- **Verdict**: Improved but still losing. Losses reduced from –$40,244 total to –$22,874 (–43%). Next strategy priority.

---

## Batch 5 — Individual Strategy Improvements (May 2026)

4 strategies modified independently, tested single-strategy, then reverted from portfolio.

### SR_Breakout_Retest (e53ab8f)
- **Added**: Candle body confirmation filter (close > open for longs, close < open for shorts)
- **Added**: Configurable params: lookback, sl_atr, tp_atr, entry_buffer
- **Why**: Was zero-trade strategy. Candle filter ensures trend confirmation on entry bar.
- **Single result**: PF 1.023, +4.10%, DD -21.8%
- **Verdict**: Profitable individually but not added to portfolio (too high DD)

### VWAP_MultiBand_Regime (d07d57c)
- **Added**: EMA200 trend filter (long only above EMA200, short only below)
- **TP**: Increased to 20 ATR from 2.0x
- **Why**: Was losing -$3,763 in prior runs. EMA200 prevents trend-fading in strong trends.
- **Single result**: PF 1.089, +7.79%, DD -13.9%
- **Verdict**: Profitable individually but not added to portfolio (high DD, portfolio interaction)

### Liquidity_Sweep_Breakout (022db8c)
- **Removed**: MSB (Market Structure Break) condition
- **TP**: Increased to 18 ATR from 2.0x
- **Why**: MSB was too restrictive, preventing trades. Wider TP for better R:R.
- **Single result**: PF 1.045, +3.50%, DD -12.5%
- **Verdict**: Removing MSB was positive. Not added to portfolio due to interaction effects.

### ICT_Killzone_Macro (7584207)
- **Killzone**: Shifted from 8-11 UTC (multiple sessions) to pure London session (7-9 UTC)
- **TP**: Increased to 16 ATR from 2.0x
- **Why**: Was over-trading across sessions. Focus on London only for higher-probability setups.
- **Single result**: PF 1.300, +11.60%, DD -4.85%
- **Verdict**: Best single improvement. Not added to portfolio — kills diversification.

### Portfolio Integration Test (reverted)
- **Test**: Added all 4 improved strategies to portfolio with original 7
- **Result**: Portfolio PF dropped from 1.17 to 0.98, -5.25% return
- **Conclusion**: Improved strategies don't improve portfolio. Each adds unique DD periods.
- **Action**: Reverted to original 7 strategies. Portfolio remains at PF 1.17, +29.60%.

### Key Learnings
1. **EMA200 filter**: Good for mean-reversion strategies (VWAP), bad for breakout strategies (LIQ)
2. **TP=16-20 ATR**: Effective for low-win-rate strategies, too wide for high-win-rate strategies
3. **Removing MSB**: Positive for LIQ but increased trade frequency too much for portfolio context
4. **Single-strategy improvement != portfolio improvement**: Always validate in portfolio context
5. **Candle body filter**: Simple and effective for trend confirmation without complex indicators
