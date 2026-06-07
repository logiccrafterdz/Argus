import json
from collections import Counter, defaultdict

for mode in ['oos_train','oos_validation','oos_test']:
    d = json.load(open(f'../docs/data/{mode}.json'))
    p = d['portfolio']
    trades = d.get('all_trades', [])
    print(f'=== {mode} ===')
    print(f'  return: {p["total_return"]}%, trades: {p["total_trades"]}, WR: {p["win_rate"]}%')
    print(f'  PF: {p["profit_factor"]}, DD: {p["max_drawdown"]}%, Sharpe: {p["sharpe_ratio"]}, Exp: {p["expectancy"]}')
    
    strat_wins = defaultdict(int)
    strat_losses = defaultdict(int)
    strat_profit = defaultdict(float)
    strat_count = Counter()
    for t in trades:
        s = t.get('strategy', '?')
        strat_count[s] += 1
        if t.get('profit', 0) > 0:
            strat_wins[s] += 1
        else:
            strat_losses[s] += 1
        strat_profit[s] += t.get('profit', 0)
    print('  --- Per Strategy ---')
    for s in sorted(strat_count.keys()):
        c = strat_count[s]
        w = strat_wins[s]
        wr = w / c * 100 if c else 0
        pr = strat_profit[s]
        print(f'  {s}: {c} trades, WR={wr:.1f}%, profit=${pr:.0f}')
    print()
