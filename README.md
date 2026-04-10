# MT5 Strategy Repository

A collection of professional MetaTrader 5 (MQL5) trading strategies and Expert Advisors. Each system is designed with a focus on market structure, institutional-grade risk management, and operational safety.

---

## Repository Structure

Each strategy is located in its own dedicated folder. This ensures a clean workspace and independent development for every trading system.

### Current Strategies:

| Strategy | Path | Technical Grade | Description |
| :--- | :--- | :--- | :--- |
| **Trend Pullback** | ./TrendPullback/ | **Production Elite** | A structure-aware trend following system. Uses 2-bar momentum confirmation and EMA confluence. |
| **S/R Break & Retest** | ./SR_Breakout_Retest/ | **Production Elite** | A multi-timeframe breakout system. Tracks S/R levels, breakouts, and retests. |
| **ORB Session** | ./ORB_Session/ | **Production Elite** | Opening Range Breakout strategy. Captures morning volatility. |
| **Bollinger Mean Rev** | ./Bollinger_MeanReversion/ | **Production Elite** | Mean reversion system using Bollinger Bands. |
| **Price Action S/R** | ./PriceAction_SR/ | **Production Elite** | Price Action rejection patterns (Pin Bar/Engulfing) at S/R levels. |
| **Liquidity Sweep** | ./Liquidity_Sweep_Breakout/ | **Production Elite** | Institutional liquidity grab system. Detects EQH/EQL and enters on MSB. |
| **VWAP Regime** | ./VWAP_MultiBand_Regime/ | **Production Elite** | Multi-VWAP Band system with ATR-based regime detection. |
| **Asian Fakeout** | ./Asian_Range_Fakeout/ | **Production Elite** | London fakeout strategy (Judas Swing) using Asian range liquidity. |
| **NY Reversal** | ./NY_Session_Reversal/ | **Production Elite** | New York session reversal strategy following London expansion. |
| **Vol Squeeze** | ./Volatility_Squeeze/ | **Production Elite** | TTM-style squeeze breakout strategy with momentum confirmation. |
| **ORB Hybrid** | ./ORB_Hybrid/ | **Production Elite** | Modern ORB system with trend bias and failure (trap) detection. |
| **Smart-Swing** | ./Smart_Swing_Bias/ | **Production Elite** | Multi-TF SMC-inspired strategy focusing on Discount/Premium zones. |
| **SuperTrend EMA** | ./SuperTrend_EMA/ | **Production Elite** | Classic SuperTrend flip strategy with 200 EMA and ATR chop filter. |
| **Hidden Div** | ./Hidden_Divergence/ | **Production Elite** | Trend continuation strategy using Hidden RSI Divergence and EMA bias. |

---

## 📈 Strategy Details

### 1. Trend Pullback (EMA)
*   **Logic**: EMA 200 trend filter + EMA 50 pullback zone.
*   **Confirmation**: 2-bar momentum sequence (Touch -> Break).
*   **Safety**: OnlyNewBar execution + Spread filter.

### 2. S/R Break & Retest
*   **Confluence Stack**: 
    *   **HTF Filter**: H4 EMA 200 determines the global bias.
    *   **Level Detection**: Radius (N bars) and Lookback parameters to identify significant local peaks/valleys.
    *   **Validation**: `MaxWaitBars` limits the wait time, and `MaxBreakDistance` tracks deviation to invalidate "tired" breakouts.
*   **Confirmation**: Price touch of the broken level followed by a directional candle close.

---

### 3. ORB Session (Opening Range Breakout)
*   **Confluence Stack**: 
    *   **Range Detection**: Automated high/low detection for a specified session window (e.g., first 30 mins).
    *   **Trend Filter**: EMA 200 on the current timeframe ensures alignment with the day's bias.
    *   **Discipline**: Strict "One Trade Per Session" rule to avoid overtrading and whipsaws.
*   **Visual Support**: Draws session range lines on the chart for transparency.

---

### 4. Bollinger Mean Reversion
*   **Confluence Stack**: 
    *   **Volatility Bands**: Bollinger Bands (20, 2.0) identify statistical extremes.
    *   **Trend Filter**: Optional EMA 200 confirmation to align mean reversion with the major trend.
    *   **Safety**: `MaxBarsOutside` limit to prevent catching a "falling knife" during parabolic trends.
    *   **RSI Filter**: Optional RSI confirmation for extreme overbought/oversold conditions.
*   **Dynamic Exit**: Take Profit targets the **Bollinger Middle Band** (The Mean), adapting to market conditions.

### 5. Price Action S/R Rejections
*   **Confluence Stack**: 
    *   **Level Synergy**: Rejections must occur within a proximity zone (5 pips) of a structural S/R level.
    *   **Candlestick Patterns**: Specialized detection for Pin Bars (long wick rejection) and Engulfing candles.
    *   **Trend Context**: Optional EMA 200 filter to prioritize trades in the direction of market flow.
*   **Disciplined Exit**: Uses a fixed 2.0 Risk-Reward ratio targeting the next structural pivot.

### 6. Liquidity Sweep & Breakout
*   **Confluence Stack**: 
    *   **Liquidity Detection**: Groups multiple swing points within a 3-pip threshold to identify EQH/EQL zones (Liquidity Pools).
    *   **Sweep Signature**: Tracks price piercing these levels and closing back within the range, identifying a "Stop Hunt" or "False Breakout".
    *   **Conservative Confirmation**: Implements a mandatory wait for a close beyond the sweep candle's range or a Market Structure Break (MSB) to avoid caught in extensions.
    *   **Trend Alignment**: Integrated EMA 200 filter to synchronize liquidity grabs with the major trend direction.
*   **Execution**: Precision "Sniper" entries with SL placed behind the sweep wick and a fixed 2.0 R:R target.

### 7. VWAP Multi-Band Regime
*   **Confluence Stack**: 
    *   **Regime Filter**: Uses the ratio `ATR / SMA(ATR)` to distinguish between "Balanced" (Range) and "Trending" (Expansion) market cycles.
    *   **Dynamic VWAP Bands**: Calculates ±1σ and ±2σ Standard Deviation bands around the Daily VWAP mean.
    *   **Thick Levels (MTF)**: Identifies high-probability zones where Daily, Weekly, and Monthly VWAP levels converge within 5 pips.
    *   **Mean Reversion logic**: Primarily executes mean reversion trades towards the VWAP during low-volatility "Balanced" regimes.
*   **Execution**: Automated TP at the VWAP mean, with safety SL beyond the outer bands.
*   **Operational Notes**:
    *   **Timezone Sync**: Daily resets and trade limits are synced to the **Broker Platform Time**. Ensure your session settings align with your target market (e.g., London/New York).
    *   **Dynamic SL Tuning**: Recommended `SL_AtrMultiplier` is between **1.0 – 2.0**. For tighter "Balanced" regimes, use smaller multipliers to maintain a positive R:R relative to the `BandMult`.

### 8. Asian Range → London Fakeout & Expansion
*   **Confluence Stack**: 
    *   **Asian Range Accumulation**: Defines the high/low context during the low-volatility Asian session (00:00 - 06:00).
    *   **London Killzone Monitoring**: Watches start of London session (08:00 - 11:00) for a liquidity grab (Fakeout).
    *   **Fakeout Detection**: Identifies price piercing Asian extremes and closing back inside (Standard Judas Swing).
    *   **Structure Confirmation**: Optional Market Structure Break (MSB) to filter false reversals.
*   **Execution**: Multi-target setup: Mid-range, Opposite side, or fixed 2.0 RR target.

### 9. New York Session Reversal (NY-Fade)
*   **Confluence Stack**: 
    *   **London Expansion Filter**: Validates that the London session (08:00 - 12:00) had a significant move (> 1.5x ATR).
    *   **NY Killzone Monitoring**: Watches the NY open window (13:00 - 15:30) for exhaustion.
    *   **Liquidity Sweep (OHLC)**: Detects price sweeping the London High/Low and closing back inside.
    *   **Market Structure Shift**: Confirms the reversal with a minor structure break (MSB) before entry.
*   **Execution**: Targets the London session midpoint (50% retracement) as a high-probability "Fair Value" return.

### 10. Volatility Squeeze Breakout
*   **Confluence Stack**: 
    *   **TTM Squeeze Engine**: Monitors Bollinger Bands (20, 2.0) coiling within Keltner Channels (20, 1.5).
    *   **Expansion Confirmation**: Requires a breakout candle to have 1.5x the average range/body size (momentum spike).
    *   **Trend Alignment**: EMA 100 filter ensures breakouts occur in the direction of the dominant trend.
    *   **Compression Filter**: Validates that the "Squeeze" has been sustained for at least 5 consecutive bars.
*   **Execution**: Targets 1:2 Risk-Reward or measured move, with SL placed at the opposite extreme of the compression zone.

### 11. ORB Hybrid / Failure EA
*   **Confluence Stack**: 
    *   **Opening Range Definition**: Capture high/low of the first 30 minutes of a session.
    *   **Trend Bias (EMA 200)**: Breakouts are only taken if they align with the higher timeframe trend.
    *   **Momentum Expansion**: Uses `ExpansionMult` to ensure the breakout candle is significant.
    *   **Failure Logic (Liquidity Sweep)**: Detects "Fakeouts" where price pierces the OR but closes back inside, triggering a reversal.
*   **Execution**: Multi-mode execution (Breakout vs Failure). TP targets 2.0x RR or the opposite OR boundary.

### 12. Multi-Timeframe Smart-Swing Bias
*   **Confluence Stack**: 
    *   **HTF Bias (PERIOD_D1)**: Enforces directional alignment with long-term trend (EMA 200/50).
    *   **Swing Leg Analysis**: Identifies the current structural high/low range on the execution timeframe.
    *   **Discount/Premium Zones**: Targets entries in the "Value Zones" (Retracements of 50%-75% of the leg).
    *   **Rejection Triggers**: Uses Price Action confirmations (Long wicks/Engulfing) for precision entry.
*   **Execution**: Aim for High Reward:Risk setups by targeting external liquidity (Swing Extremes) with a fixed 2.0+ RR.

### 13. SuperTrend + EMA Confluence
*   **Confluence Stack**: 
    *   **Institutional Bias (EMA 200)**: Ensures all trades occur within the major market regime.
    *   **SuperTrend Adaptive Engine**: Detects trend flips using ATR-adjusted price bands for dynamic S/R.
    *   **Chop Filter (ATR Regime)**: Prevents entry during low-volatility "dead zones" where trend-following fails.
    *   **Dynamic Trailing SL**: Automatically lock in profits by moving the stop loss along the SuperTrend line.
*   **Execution**: Enters at close of the flip candle. Exit via Trailing SL or optional 1:2 RR.

### 14. Hidden Divergence + Trend Confluence
*   **Confluence Stack**: 
    *   **Institutional Bias (EMA 200)**: Operates strictly in the direction of the higher timeframe trend.
    *   **Hidden Bullish Div**: Detects Price Higher-Low vs RSI Lower-Low (Springboard setup).
    *   **Hidden Bearish Div**: Detects Price Lower-High vs RSI Higher-High (Exhaustion setup).
    *   **Swing Logic**: Uses structural peaks and troughs to ensure high-fidelity signal mapping.
*   **Execution**: Triggered upon confirmation of the second swing point. SL placed at the structural extreme.

---

## Getting Started

1. Download the strategy folder and place it in your MetaTrader 5 MQL5/Experts directory.
2. Ensure you have the necessary libraries (`StructureUtils.mqh`) included.
3. Always test the strategy on a Demo account before moving to a Live environment.

> [!NOTE]
> **Pips Definition**: All distance parameters (e.g., `MaxSR_DistancePips`) are based on the standard 5/3 digit broker logic. If your broker uses 5 digits, 1.0 Pip = 10 Points.

---

## LEGAL DISCLAIMER - PLEASE READ CAREFULLY

### USE AT YOUR OWN RISK
The software, Expert Advisors (EAs), indicators, and strategies contained in this repository are provided for **educational and informational purposes only**. They do not constitute financial, investment, or trading advice.

### No Warranty
This software is provided "as is", without warranty of any kind, express or implied. In no event shall the authors or copyright holders be liable for any claim, damages, or other liability.

### Trading Risks
Trading financial instruments involves a high level of risk. You may lose some or all of your initial investment. Past performance is not indicative of future results.

---

## License
This project is licensed under the MIT License - see the LICENSE file for details.
