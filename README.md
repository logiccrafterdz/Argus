# MT5 Strategy Repository

A collection of professional MetaTrader 5 (MQL5) trading strategies and Expert Advisors. Each system is designed with a focus on market structure, institutional-grade risk management, and operational safety.

---

## Repository Structure

Each strategy is located in its own dedicated folder. This ensures a clean workspace and independent development for every trading system.

### Current Strategies:

| Strategy | Path | Technical Grade | Description |
| :--- | :--- | :--- | :--- |
| **Trend Pullback (Standard Gold)** | ./TrendPullback/ | **Production Elite** | A structure-aware trend following system. Uses 2-bar momentum confirmation, EMA confluence, and HH/HL detection. |

---

## 💎 Project Highlights: Standard Gold Quality

All strategies in this repository (starting with the Trend Pullback v3.1) adhere to the **Standard Gold** implementation criteria:
*   **Structure-Aware:** Filters trends based on actual High/Low market structure.
*   **Execution Control:** New Bar processing to avoid noise and redundant triggers.
*   **Broker Safety:** Automatic validation and adjustment for `STOPS_LEVEL` and `FREEZE_LEVEL`.
*   **Dynamic Precision:** Lot sizes and prices are normalized dynamically based on broker-specific symbols.

---

## Getting Started

1. Download the strategy folder and place it in your MetaTrader 5 MQL5/Experts directory.
2. Ensure you have the necessary libraries (`StructureUtils.mqh`) included.
3. Always test the strategy on a Demo account before moving to a Live environment.

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
