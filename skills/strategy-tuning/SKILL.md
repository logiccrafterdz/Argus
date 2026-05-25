---
name: strategy-tuning
description: >
  Guidelines and historical learnings for tuning individual trading strategies.
  Use when modifying any strategy file in backtest/strategies/ to understand
  what has been tried, what worked, and what didn't.
---

# Strategy Tuning

## General Rules

1. **ATR-based parameters** over fixed values:
   - SL: `1.0 × ATR` as default, widen to `1.5 × ATR` if too many stop-outs
   - TP: `2.0 × ATR` as minimum, `3.0 × ATR` for trending conditions
   - Buffer/entry filters: `0.3 - 0.5 × ATR`
   - Use `self._atr_buf(df, i-1, multiplier)` from BaseStrategy

2. **R:R ratio**: Target minimum 1:2 (risk:reward). 1:3 for strategies with lower win rates. Never go below 1:1.5.

3. **Lookback periods**: Shorter lookbacks capture more trades but increase noise. Start at 10-20 and adjust based on signal quality.

4. **Zero-trade strategies**: If a strategy makes 0 trades, relax entry conditions or reduce lookback. Check that the indicator values are being computed correctly.

## Historical Tuning Log

### Run 1 (Initial, no changes)
- 20 strategies, all with various original parameters
- Portfolio: net_profit = -$50,525, WR = 62.4%, PF = 0.46, max DD = -51.1%
- Only ORB_Hybrid and ICT_Killzone_Macro were profitable

### Run 2 (First batch — easier parameter tweaks)
- **SR_Breakout_Retest**: lookback 40→5, buffer 0.5→1.0×ATR, relaxed retest condition
- **ADX_TrendStrength**: ADX threshold 25→20
- **Donchian_Breakout**: period 20→10, EMA 50→20
- **Liquidity Sweep FVG**: fixed threshold→ATR-based 0.5×
- **ORB_Session**: orb_duration 30→15 min
- Result: still ~$50K loss, minimal change

### Run 3 (Second batch — ATR-based SL/TP for ALL strategies)
- Added ATR-based SL/TP to: AVWAP_Confluence, PDH_PDL_BreakReversal, Asian_Range_Fakeout, VWAP_MultiBand_Regime, Volatility_Squeeze, PriceAction_SR, NY_Session_Reversal, Smart_Swing_Bias, Liquidity_Sweep_Breakout, SuperTrend_EMA, TrendPullback, Bollinger_MR
- Results: Smart_Swing_Bias and PriceAction_SR got worse; Bollinger_MR stopped trading
- Net: -$50,055 (+$470 improvement) — essentially no change

### Run 4 (Third batch — fix strategies that got worse)
- Smart_Swing_Bias: SL widened to 1.5×ATR, TP to 3.0×ATR
- PriceAction_SR: SL to 1.0×ATR, buffer to 0.5×ATR
- Bollinger_MR: SL to 1.5×ATR, TP to 3.0×ATR
- Liquidity Sweep FVG: ATR-based SL/TP (1:2 R:R)
- SR_Breakout_Retest: lookback 5→10, buffer 1.0→0.3×ATR
- Donchian_Breakout: period 10→5, EMA 20→10, ATR-based SL/TP, start_idx 50→20
- Result: -$50,701, WR 62.5%, PF 0.46 — identical to Run 1

## Key Insight

After 4 runs and 20+ strategy modifications, the portfolio metrics barely changed:
net_profit hovered between -$50K and -$50.7K (±1%). This means:

**Strategy parameter tuning has reached diminishing returns.**

The core problem is NOT individual strategy parameters but portfolio-level:
1. All strategies lose during Q1-Q2 2022 (Fed hiking cycle, Ukraine war)
2. The portfolio dies by May 2022 and never recovers
3. Correlation between losing strategies amplifies the drawdown

## Next Steps (Not Yet Attempted)

1. **Portfolio-level circuit breaker**: Stop trading when DD exceeds 30%, resume only when conditions improve
2. **Dynamic position sizing**: Scale down as DD increases, scale up when equity grows
3. **Market regime filter**: Skip trading during high-volatility regimes (2022-style)
4. **Strategy selection**: Drop the worst 3-5 strategies, increase allocation to the best 2
5. **Walk-forward optimization**: Test parameters on rolling windows instead of full history
