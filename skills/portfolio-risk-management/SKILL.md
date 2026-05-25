---
name: portfolio-risk-management
description: >
  Guidelines for portfolio-level risk management in the Argus backtest system.
  Covers circuit breakers, correlation handling, position sizing, and market
  regime detection. Use when modifying engine.py, risk_manager.py, or config.yaml.
---

# Portfolio Risk Management

## Current State (as of May 2026)

### What's Implemented
- **Risk Manager** (`backtest/risk_manager.py`):
  - Daily/Weekly/Monthly drawdown limits (3%/8%/15%)
  - Position halt when limits exceeded
  - Per-symbol exposure limit (max 2 positions per symbol)
  - Correlation check (threshold 0.8) via correlation_matrix

- **Backtest Engine** (`backtest/engine.py`):
  - Bankruptcy detection (<5% initial balance = bankrupt, stops all trading)
  - Max drawdown detection (>50% from peak balance = bankrupt)
  - Breakeven logic at 1R profit
  - Partial close at 1.5R (50% of position)
  - 3x leverage cap per trade
  - Commission, slippage, spread modeling

### What's Missing (Key Findings)

1. **No dynamic circuit breaker**: Once DD limits are hit, trading halts permanently until next day. There's no gradual position scaling based on current DD level.

2. **No volatility-based position sizing**: Lot size is based on fixed 1% risk_percent_per_trade, regardless of market volatility regime.

3. **All strategies lose simultaneously**: In Q1-Q2 2022, ALL strategies lost money, indicating a systemic market regime problem that per-strategy tuning cannot fix.

4. **Bankruptcy ends everything**: Once bankrupt, no more trades execute. The system doesn't reduce positions gradually or switch to defensive mode.

5. **No market regime override**: The regime_mask exists per-strategy but there's no global "high-volatility regime" mode that reduces position sizes across all strategies.

## Proposed Improvements (Not Yet Implemented)

### Circuit Breaker Enhancements
```
- Graduated DD response:
  - DD > 10%: reduce position size to 75%
  - DD > 20%: reduce position size to 50%
  - DD > 30%: reduce position size to 25%
  - DD > 40%: close all positions, stop trading, enter recovery mode
- Recovery mode: trade only the 2 best-performing strategies at 0.5x size until DD < 15%
```

### Dynamic Position Sizing
```
- Base risk = 1.0% per trade
- Volatility multiplier = max(0.5, 14_ATR / 20_ATR)  # shrank when vol spikes
- Correlation penalty: if 3+ correlated strategies enter same direction same day, reduce size by 20% each
- Drawdown multiplier: linear reduction as DD increases (1.0 at 0% DD, 0.2 at 40% DD)
```

### Market Regime Detection
```
- Trend Strength Index (ADX) across portfolio:
  - ADX > 30: Trending regime → favor trend-following strategies
  - ADX 20-30: Normal → all strategies
  - ADX < 20: Ranging regime → favor mean-reversion strategies
- Global volatility regime:
  - Average ATR(14) across all symbols vs 50-period average
  - High vol: reduce all position sizes by 50%
```

## Lessons Learned

1. **Fix the portfolio first, then individual strategies**. If all strategies lose money in the same period, no amount of per-strategy tuning will help.
2. **Correlation neglect is dangerous**. When correlated strategies all enter similar positions, a small adverse move hits the portfolio disproportionately hard.
3. **The best defense is not trading**. A circuit breaker that halts trading during high DD is worth more than any single strategy improvement.
4. **Partial closes help but aren't enough**. The 1.5R partial close protects profits on winning trades but doesn't help during sustained losing streaks.
