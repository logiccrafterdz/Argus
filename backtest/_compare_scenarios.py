import json
import os

scenarios = {
    'A (Baseline)': '../docs/data/results_A_Baseline.json',
    'B (Sentiment)': '../docs/data/results_B_Sentiment.json',
    'C (RL Agent)': '../docs/data/results_C_RL_Agent.json',
    'D (Both)': '../docs/data/results_D_Both.json',
}

print(f"{'Scenario':<15} | {'Net Profit':<12} | {'PF':<6} | {'Trades':<8} | {'Win Rate':<10} | {'Max DD':<8} | {'Sharpe':<8}")
print("-" * 80)

for name, path in scenarios.items():
    if not os.path.exists(path):
        print(f"{name:<15} | MISSING")
        continue
    
    with open(path, 'r') as f:
        d = json.load(f)
        p = d.get('portfolio', {})
        
        profit = p.get('net_profit', 0)
        pf = p.get('profit_factor', 0)
        trades = p.get('total_trades', 0)
        wr = p.get('win_rate', 0)
        dd = p.get('max_drawdown', 0)
        sharpe = p.get('sharpe_ratio', 0)
        
        print(f"{name:<15} | ${profit:<11.2f} | {pf:<6.2f} | {trades:<8} | {wr:>5.1f}%     | {dd:>6.2f}% | {sharpe:>6.2f}")
