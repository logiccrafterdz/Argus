"""
Analyze backtest results from docs/data/results.json and print key insights.

Usage:
    python skills/scripts/analyze_results.py

This script extracts portfolio and per-strategy metrics, identifies the
biggest winners and losers, and suggests next steps based on the data.
"""
import json
import os

RESULTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "docs", "data", "results.json"
)

def load_results():
    if not os.path.exists(RESULTS_PATH):
        print(f"Results file not found: {RESULTS_PATH}")
        return None
    with open(RESULTS_PATH) as f:
        return json.load(f)

def print_portfolio_summary(data):
    p = data.get("portfolio", {})
    print("=" * 50)
    print("PORTFOLIO SUMMARY")
    print("=" * 50)
    print(f"  Net Profit:     ${p.get('net_profit', 0):,.2f}")
    print(f"  Total Return:   {p.get('total_return', 0):.1f}%")
    print(f"  Total Trades:   {p.get('total_trades', 0)}")
    print(f"  Win Rate:       {p.get('win_rate', 0):.1f}%")
    print(f"  Profit Factor:  {p.get('profit_factor', 0):.2f}")
    print(f"  Max Drawdown:   {p.get('max_drawdown', 0):.1f}%")
    print(f"  Sharpe:         {p.get('sharpe_ratio', 0):.2f}")
    print(f"  Expectancy:     ${p.get('expectancy', 0):.2f}")
    print()

def print_strategy_summary(data):
    strategies = data.get("strategies", [])
    if not strategies:
        print("No strategy data found.")
        return

    # Sort by net profit ascending (worst first)
    sorted_strats = sorted(strategies, key=lambda s: s.get("net_profit", 0))

    print("=" * 80)
    print(f"{'STRATEGY':<30} {'NET PROFIT':>12} {'TRADES':>8} {'WR%':>7} {'PF':>7}")
    print("-" * 80)
    total_pnl = 0
    for s in sorted_strats:
        pnl = s.get("net_profit", 0)
        total_pnl += pnl
        print(
            f"{s['name']:<30} ${pnl:>+8,.2f}  {s['total_trades']:>5}  "
            f"{s['win_rate']:>5.1f}%  {s['profit_factor']:>5.2f}"
        )
    print("-" * 80)
    print(f"{'TOTAL':<30} ${total_pnl:>+8,.2f}")

def suggest_next_steps(data):
    strategies = data.get("strategies", [])
    sorted_strats = sorted(strategies, key=lambda s: s.get("net_profit", 0))

    print()
    print("=" * 50)
    print("NEXT STEPS SUGGESTIONS")
    print("=" * 50)

    # Worst 3 strategies
    worst = sorted_strats[:3]
    print("\nTop 3 strategies to fix (biggest losers):")
    for s in worst:
        print(f"  {s['name']}: ${s['net_profit']:,.2f} ({s['total_trades']} trades)")

    # Zero-trade strategies
    zero = [s for s in strategies if s.get("total_trades", 0) == 0]
    if zero:
        print("\nZero-trade strategies (need code fix):")
        for s in zero:
            print(f"  {s['name']}")

    # Best 2 strategies
    best = sorted_strats[-3:]
    print("\nTop strategies (focus here):")
    for s in reversed(best):
        if s.get("net_profit", 0) > 0:
            print(f"  {s['name']}: +${s['net_profit']:,.2f}")

    # Portfolio-level observations
    p = data.get("portfolio", {})
    if p.get("max_drawdown", 0) < -30:
        print("\nPortfolio risk alert:")
        print(f"  Max DD is {p['max_drawdown']:.1f}% — needs circuit breaker")
    if p.get("profit_factor", 1) < 1.0:
        print(f"  Profit Factor is {p['profit_factor']:.2f} — portfolio is not profitable")

def main():
    data = load_results()
    if not data:
        return
    print_portfolio_summary(data)
    print_strategy_summary(data)
    suggest_next_steps(data)

if __name__ == "__main__":
    main()
