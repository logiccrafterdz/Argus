import os, sys, pandas as pd, numpy as np, json, random
sys.path.insert(0, os.path.dirname(__file__))
from engine import BacktestEngine
from analytics import calculate_metrics
from config import load_config, create_default_config
from log_setup import setup_logger
from strategies.avwap_confluence import AVWAPConfluence
from strategies.adx_trend_strength import ADXTrendStrength
from strategies.hidden_divergence import HiddenDivergence
from strategies.donchian_breakout import DonchianBreakout
from strategies.bollinger_mr import BollingerMeanReversion
from strategies.smart_swing_bias import SmartSwingBias
from strategies.price_action_sr import PriceActionSR
from indicators import MarketRegime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SPLITS = {
    'train':      {'start': '2017-01-01', 'end': '2023-01-01', 'label': 'TRAIN'},
    'validation': {'start': '2023-01-01', 'end': '2024-01-01', 'label': 'VAL'},
    'test':       {'start': '2024-01-01', 'end': '2026-06-01', 'label': 'TEST'},
}

def load_data():
    d = {}
    for fn in os.listdir(DATA_DIR):
        if not fn.endswith('.csv'): continue
        s, tf = fn.split('.')[0].split('_')
        df = pd.read_csv(os.path.join(DATA_DIR, fn), parse_dates=['time']).set_index('time')
        d.setdefault(s, {})[tf] = df
    return d

def run_portfolio(mode, logger):
    sp = SPLITS[mode]
    config = load_config()
    if config is None: config = create_default_config()
    data = load_data()
    engine = BacktestEngine(initial_balance=100000.0, config=config)
    strategies = [AVWAPConfluence(), ADXTrendStrength(), HiddenDivergence(),
                  DonchianBreakout(), BollingerMeanReversion(), SmartSwingBias(), PriceActionSR()]
    for s in strategies:
        if s.disable_breakeven: engine.disable_breakeven_strategies.add(s.name)
    master = None
    for s, tfs in data.items():
        idx = pd.Series(index=(tfs['M15'] if 'M15' in tfs else tfs['H1']).index, dtype=float)
        master = idx if master is None else master.combine_first(idx)
    master = master.sort_index()
    master = master[(master.index >= sp['start']) & (master.index < sp['end'])]
    precalc = {}
    for s, tfs in data.items():
        precalc[s] = {}
        for strat in strategies:
            tf = 'H1'
            if strat.name in ['PriceAction_SR', 'Donchian_Breakout', 'Smart_Swing_Bias']: tf = 'H4'
            if tf in tfs:
                df = tfs[tf].copy().reset_index()
                df = strat.prepare_data(df).set_index('time')
                precalc[s].setdefault(tf, {})[strat.name] = df
    regimes = {}
    for s in data:
        for tf in ['H4', 'H1']:
            if tf in data[s] and len(data[s][tf]) >= 20:
                d1 = data[s][tf].resample('D').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
                if len(d1) >= 20: regimes[s] = MarketRegime(d1).to_dict()
                break
        if s not in regimes: regimes[s] = {}
    all_syms = list(data.keys())
    h1c = {sym: data[sym]['H1']['close'] for sym in all_syms if 'H1' in data[sym]}
    corr_m = pd.DataFrame(h1c).corr()
    dict_d = {sym: {tf: df.to_dict('index') for tf, df in tfs.items()} for sym, tfs in data.items()}
    dict_p = {}
    for s, tfs in precalc.items():
        dict_p[s] = {}
        for tf, sd in tfs.items():
            dict_p[s][tf] = {sn: df.to_dict('index') for sn, df in sd.items()}
    for ci, ct in enumerate(master.index):
        if ci % 30000 == 0: logger.info(f'{ci}/{len(master)}')
        cp, ch, cl = {}, {}, {}
        for s, tfs in dict_d.items():
            for tf in ['M15', 'H1']:
                if tf in tfs and ct in tfs[tf]:
                    r = tfs[tf][ct]; cp[s]=r['close']; ch[s]=r['high']; cl[s]=r['low']; break
        cd = ct.normalize()
        cs_sess = 0; h = ct.hour
        if 0 <= h < 8: cs_sess |= 1
        if 8 <= h < 16: cs_sess |= 2
        if 13 <= h < 22: cs_sess |= 4
        engine.update(ct, cp, ch, cl)
        if engine.risk_manager.is_halted: continue
        for s, tfs in dict_p.items():
            if s not in cp: continue
            for tf, sd in tfs.items():
                if tf == 'M15' and ('M15' not in dict_d[s] or ct not in dict_d[s]['M15']): continue
                if tf == 'H1' and (ct.minute != 0 or 'H1' not in dict_d[s] or ct not in dict_d[s]['H1']): continue
                if tf == 'H4' and (ct.minute != 0 or ct.hour % 4 != 0 or 'H4' not in dict_d[s] or ct not in dict_d[s]['H4']): continue
                for strat in strategies:
                    if strat.name not in sd: continue
                    sr = regimes.get(s, {}).get(cd, 1)
                    if not strat.check_regime(sr) or not strat.check_session(cs_sess): continue
                    row = sd[strat.name].get(ct)
                    if not row or row['signal'] == 0: continue
                    side = 'BUY' if row['signal'] == 1 else 'SELL'
                    rd = (cp[s] - row['sl']) if side == 'BUY' else (row['sl'] - cp[s])
                    if rd <= 0 or pd.isna(rd): continue
                    if not engine.risk_manager.check_correlation(s, side, engine.open_positions, corr_m, 0.8): continue
                    lot = engine.calculate_lot_size(s, 0.2, rd, engine.equity)
                    engine.execute_trade(s, strat.name, side, lot, cp[s], row['sl'], row['tp'], 'Sig')
    engine.emergency_close_all(cp if cp else {})
    return engine.closed_trades

def mc_simulation(trades, n_sims=1000):
    profits = np.array([t['profit'] for t in trades])
    n = len(profits)
    results = []
    for _ in range(n_sims):
        shuffled = np.random.choice(profits, size=n, replace=True)
        eq = 100000.0 + np.cumsum(shuffled)
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / peak * 100
        results.append({
            'net_profit': float(np.sum(shuffled)),
            'max_dd': float(np.min(dd)),
            'final': float(eq[-1]),
        })
    df = pd.DataFrame(results)
    pct_pos = (df['net_profit'] > 0).mean() * 100
    return {
        'n_simulations': n_sims,
        'pct_profitable': pct_pos,
        'avg_net_profit': df['net_profit'].mean(),
        'median_net_profit': df['net_profit'].median(),
        'std_net_profit': df['net_profit'].std(),
        'actual_net_profit': float(np.sum(profits)),
        'worst_5pct': df['net_profit'].quantile(0.05),
        'best_5pct': df['net_profit'].quantile(0.95),
        'avg_max_dd': df['max_dd'].mean(),
        'worst_max_dd': df['max_dd'].min(),
        'pct_dd_gt_20pct': (df['max_dd'] < -20).mean() * 100,
        'pct_dd_gt_30pct': (df['max_dd'] < -30).mean() * 100,
    }

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    modes = ['train', 'validation', 'test'] if mode == 'all' else [mode]
    for m in modes:
        logger = setup_logger(f'mc_{m}')
        print(f"\n{'='*60}")
        print(f"  MONTE CARLO: {SPLITS[m]['label']}")
        print(f"{'='*60}")
        trades = run_portfolio(m, logger)
        print(f"  Actual trades collected: {len(trades)}")
        mc = mc_simulation(trades, n_sims=2000)
        print(f"\n  {'Metric':<30} {'Value':<15}")
        print(f"  {'-'*45}")
        print(f"  {'Simulations':<30} {mc['n_simulations']:<15}")
        print(f"  {'Profitable (% of sims)':<30} {mc['pct_profitable']:<14.1f}%")
        print(f"  {'Actual Net Profit':<30} ${mc['actual_net_profit']:<+11.2f}")
        print(f"  {'Avg Net Profit (sims)':<30} ${mc['avg_net_profit']:<+11.2f}")
        print(f"  {'Median Net Profit':<30} ${mc['median_net_profit']:<+11.2f}")
        print(f"  {'Std Dev Net Profit':<30} ${mc['std_net_profit']:<+11.2f}")
        print(f"  {'Worst 5%':<30} ${mc['worst_5pct']:<+11.2f}")
        print(f"  {'Best 5%':<30} ${mc['best_5pct']:<+11.2f}")
        print(f"  {'Avg Max DD':<30} {mc['avg_max_dd']:<14.2f}%")
        print(f"  {'Worst Max DD (sims)':<30} {mc['worst_max_dd']:<14.2f}%")
        print(f"  {'DD > 20% (% of sims)':<30} {mc['pct_dd_gt_20pct']:<14.1f}%")
        print(f"  {'DD > 30% (% of sims)':<30} {mc['pct_dd_gt_30pct']:<14.1f}%")
