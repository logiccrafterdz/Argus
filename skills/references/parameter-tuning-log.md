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

## Batch 4 — TBD (Portfolio-level changes)

Next changes should focus on portfolio-level risk, not individual strategies.
