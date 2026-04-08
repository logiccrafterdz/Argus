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
