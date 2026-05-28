"""
Analyze backtest results from docs/data/results.json and print key insights.
Includes composite scoring from scoring.py.

Usage:
    python skills/scripts/analyze_results.py
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scoring import PortfolioScorer, StrategyScorer, load_results, score_all_strategies

RESULTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "docs", "data", "results.json"
)

def main():
    data = load_results(RESULTS_PATH)
    if not data:
        print(f"Results not found: {RESULTS_PATH}")
        return 1

    p = data.get("portfolio", {})
    ps = PortfolioScorer.score(p)

    print("=" * 60)
    print("  PORTFOLIO SUMMARY + COMPOSITE SCORE")
    print("=" * 60)
    print(f"  Net Profit:     ${p.get('net_profit', 0):>+,.2f}")
    print(f"  Total Return:   {p.get('total_return', 0):>+.1f}%")
    print(f"  Total Trades:   {p.get('total_trades', 0)}")
    print(f"  Win Rate:       {p.get('win_rate', 0):>5.1f}%")
    print(f"  Profit Factor:  {p.get('profit_factor', 0):>5.2f}")
    print(f"  Max Drawdown:   {p.get('max_drawdown', 0):>+.1f}%")
    print(f"  Sharpe:         {p.get('sharpe_ratio', 0):>5.2f}")
    print(f"  Expectancy:     ${p.get('expectancy', 0):>+7.2f}")
    print(f"  Score:          {ps['composite']:.1f}/100  Grade: {ps['grade']}")
    print(f"  Sub-scores:     {', '.join(f'{k}={v:.0f}' for k,v in ps['sub_scores'].items())}")
    print()

    scored = score_all_strategies(data)
    print("=" * 75)
    print(f"{'STRATEGY':<28} {'SCORE':>6} {'GRADE':>6} {'NET P&L':>10} {'TRADES':>7} {'WR%':>6} {'PF':>6}")
    print("-" * 75)
    for s in scored:
        sc = s["score"]
        pnl = s.get("net_profit", 0)
        print(f"{s['name']:<28} {sc['composite']:>6.1f} {sc['grade']:>6} ${pnl:>+8,.0f} {s['total_trades']:>7} {s['win_rate']:>5.1f}% {s['profit_factor']:>6.2f}")
    print("-" * 75)

    # Recommendations
    worst = scored[-1]
    best = scored[0]
    zero = [s for s in data.get("strategies", []) if s.get("total_trades", 0) == 0]
    print()
    print("=" * 40)
    print("  RECOMMENDATIONS")
    print("=" * 40)
    print(f"  Focus on: {best['name']} (score {best['score']['composite']:.1f})")
    print(f"  Fix: {worst['name']} (score {worst['score']['composite']:.1f}, PF {worst['profit_factor']:.2f})")
    if zero:
        print(f"  Investigate zero-trade: {', '.join(s['name'] for s in zero)}")
    if p.get('profit_factor', 1) < 1.0:
        print(f"  Portfolio PF is {p['profit_factor']:.2f} — needs improvement")
    if abs(p.get('max_drawdown', 0)) > 15:
        print(f"  High DD ({p['max_drawdown']:.1f}%) — consider circuit breaker")

    return 0

if __name__ == "__main__":
    sys.exit(main())
