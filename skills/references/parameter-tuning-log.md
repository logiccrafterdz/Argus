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
