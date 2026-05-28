# Per-Strategy P&L Breakdown (Run 6 — May 2026)

Ordered by net profit (best to worst):

| Rank | Strategy | Category | Net Profit | Trades | WR% | PF | Score |
|------|----------|----------|-----------|-------|-----|-----|-------|
| 1 | Bollinger Mean Reversion | Mean Reversion | +$12,900 | 239 | 38.9% | 1.36 | 73.4 B |
| 2 | PriceAction_SR | Price Action | +$10,316 | 99 | 32.3% | 1.69 | 76.0 B |
| 3 | AVWAP_Confluence | Institutional | +$8,183 | 353 | 21.2% | 1.12 | 63.8 B |
| 4 | Hidden_Divergence | Divergence | +$4,578 | 93 | 31.2% | 1.31 | 67.2 B |
| 5 | ADX_TrendStrength | Trend Following | +$765 | 27 | 18.5% | 1.15 | 55.6 C |
| 6 | Smart_Swing_Bias | Trend Following | +$189 | 56 | 39.3% | 1.03 | 58.6 C |
| 7 | Donchian_Breakout | Breakout | -$7,331 | 182 | 28.6% | 0.75 | 52.0 C |

**TOTAL**: +$29,599, 1,049 trades, PF 1.17, DD -5.38%

## Key Observations
- **Top 3 contribute 106% of profits** (Bollinger + PriceAction + AVWAP cover losses from Donchian)
- **Donchian_Breakout** is the only losing strategy — PF 0.75, losing -$7,331
- **6 of 7 strategies profitable** — first time in project history
- **Diversification works**: despite mixed individual PFs, portfolio DD is only -5.38%

## Improvement Priority
1. **Donchian_Breakout**: Fix PF from 0.75 to > 1.0 (potential +$7,331 gain)
2. **Smart_Swing_Bias**: Low profit but barely positive (PF 1.03) — needs parameter tuning
3. **ADX_TrendStrength**: Only 27 trades — needs more signals
