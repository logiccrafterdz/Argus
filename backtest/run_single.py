"""
Single-strategy backtest runner for iterative optimization.
Usage: python backtest/run_single.py StrategyName
Example: python backtest/run_single.py SuperTrendEMA
"""
import os, sys, json, argparse, importlib
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import BacktestEngine
from analytics import calculate_metrics
from json_encoder import NumpyEncoder
from indicators import MarketRegime
from config import load_config, create_default_config
from log_setup import setup_logger

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "data")
STRATEGY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strategies")

def load_data():
    symbols_data = {}
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".csv"):
            symbol, tf = filename.split('.')[0].split('_')
            filepath = os.path.join(DATA_DIR, filename)
            df = pd.read_csv(filepath, parse_dates=['time'])
            df.set_index('time', inplace=True)
            if symbol not in symbols_data:
                symbols_data[symbol] = {}
            symbols_data[symbol][tf] = df
    return symbols_data

NAME_TF_MAP = {
    'ICT_Killzone_Macro': 'M15', 'ORB_Session': 'M15', 'ORB_Hybrid': 'M15',
    'Asian_Range_Fakeout': 'M15', 'NY_Session_Reversal': 'M15', 'PDH_PDL_BreakReversal': 'M15',
    'PriceAction_SR': 'H4', 'Donchian_Breakout': 'H4', 'Smart_Swing_Bias': 'H4',
}

def get_strategy_tf(strat_name):
    return NAME_TF_MAP.get(strat_name, 'H1')

def build_master_timeline(data):
    master = None
    for symbol, tfs in data.items():
        if 'M15' in tfs:
            idx = pd.Series(index=tfs['M15'].index, dtype=float)
        elif 'H1' in tfs:
            idx = pd.Series(index=tfs['H1'].index, dtype=float)
        else:
            continue
        if master is None:
            master = idx
        else:
            master = master.combine_first(idx)
    return master.sort_index()

def run_single(strat_class, label=None):
    logger = setup_logger('single')
    config = load_config() or create_default_config()
    init_balance = config.get('backtest', {}).get('initial_balance', 100000.0)

    strat = strat_class()
    name = label or strat.name
    tf = get_strategy_tf(name)

    logger.info(f"Loading data for single strategy: {name} (tf={tf})")
    data = load_data()
    logger.info(f"Symbols: {len(data)}")

    engine = BacktestEngine(initial_balance=init_balance, config=config)
    if strat.disable_breakeven:
        engine.disable_breakeven_strategies.add(name)
    master_timeline = build_master_timeline(data)

    # Precalculate signals for this strategy only
    logger.info("Precalculating signals...")
    precalc = {}
    for symbol, tfs in data.items():
        if tf not in tfs:
            continue
        df = tfs[tf].copy()
        df.reset_index(inplace=True)
        df = strat.prepare_data(df)
        df.set_index('time', inplace=True)
        precalc[symbol] = {tf: {name: df.to_dict('index')}}

    # Regime
    regimes = {}
    for sym in data:
        if 'H4' in data[sym]:
            h4 = data[sym]['H4']
            d1 = h4.resample('D').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
            mr = MarketRegime(d1)
            regimes[sym] = mr.to_dict()
        elif 'H1' in data[sym]:
            h1 = data[sym]['H1']
            d1 = h1.resample('D').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
            mr = MarketRegime(d1)
            regimes[sym] = mr.to_dict()
        else:
            regimes[sym] = {}

    # Correlation
    symbols = list(data.keys())
    h1c = {}
    for sym in symbols:
        if 'H1' in data[sym]:
            h1c[sym] = data[sym]['H1']['close']
    corr_df = pd.DataFrame(h1c)
    corr_matrix = corr_df.corr()

    # Dict conversion
    data_dict = {}
    for sym, tfs in data.items():
        data_dict[sym] = {}
        for tfn, df in tfs.items():
            data_dict[sym][tfn] = df.to_dict('index')

    # Execute
    logger.info("Executing backtest...")
    total = len(master_timeline)
    trade_count = 0
    for idx, current_time in enumerate(master_timeline.index):
        if idx % 20000 == 0 and idx > 0:
            logger.info(f"Progress: {idx}/{total}")

        prices, highs, lows = {}, {}, {}
        for sym, tfs in data_dict.items():
            if 'M15' in tfs and current_time in tfs['M15']:
                r = tfs['M15'][current_time]
                prices[sym], highs[sym], lows[sym] = r['close'], r['high'], r['low']
            elif 'H1' in tfs and current_time in tfs['H1']:
                r = tfs['H1'][current_time]
                prices[sym], highs[sym], lows[sym] = r['close'], r['high'], r['low']

        cdate = current_time.normalize()
        h = current_time.hour
        c_session = (1 if 0 <= h < 8 else 0) | (2 if 8 <= h < 16 else 0) | (4 if 13 <= h < 22 else 0)

        engine.update(current_time, prices, highs, lows)
        if engine.risk_manager.is_halted:
            continue

        # Only for this strategy's tf at correct interval
        if tf == 'H1' and current_time.minute != 0:
            continue
        if tf == 'H4' and (current_time.minute != 0 or current_time.hour % 4 != 0):
            continue

        sym_regime = regimes.get(list(prices.keys())[0] if prices else '', {}) if len(prices) == 1 else {}
        c_regime = sym_regime.get(cdate, 1)
        if not strat.check_regime(c_regime) or not strat.check_session(c_session):
            continue

        for symbol in prices:
            if symbol not in precalc or tf not in precalc[symbol] or name not in precalc[symbol][tf]:
                continue
            row = precalc[symbol][tf][name].get(current_time)
            if row is None:
                continue

            sig = row['signal']
            if sig == 1:
                rd = prices[symbol] - row['sl']
                if rd <= 0 or pd.isna(rd):
                    continue
                if not engine.risk_manager.check_correlation(symbol, 'BUY', engine.open_positions, corr_matrix, 0.8):
                    continue
                lot = engine.calculate_lot_size(symbol, 0.2, rd, engine.equity)
                engine.execute_trade(symbol, name, 'BUY', lot, prices[symbol], row['sl'], row['tp'], "Buy")
                trade_count += 1
            elif sig == -1:
                rd = row['sl'] - prices[symbol]
                if rd <= 0 or pd.isna(rd):
                    continue
                if not engine.risk_manager.check_correlation(symbol, 'SELL', engine.open_positions, corr_matrix, 0.8):
                    continue
                lot = engine.calculate_lot_size(symbol, 0.2, rd, engine.equity)
                engine.execute_trade(symbol, name, 'SELL', lot, prices[symbol], row['sl'], row['tp'], "Sell")
                trade_count += 1

    logger.info(f"Backtest done. Trades executed: {trade_count}")

    # Always close remaining
    engine.emergency_close_all(prices if prices else {})

    # Metrics
    port = calculate_metrics(engine.closed_trades, engine.equity_curve, init_balance)
    for k, v in port.items():
        if hasattr(v, 'item'):
            port[k] = v.item()

    trades = len(engine.closed_trades)
    df_t = pd.DataFrame(engine.closed_trades) if trades > 0 else pd.DataFrame()
    if not df_t.empty:
        wins = df_t[df_t['profit'] > 0]
        losses = df_t[df_t['profit'] <= 0]
        wr = len(wins) / trades * 100 if trades > 0 else 0
        gp = wins['profit'].sum() if len(wins) > 0 else 0
        gl = abs(losses['profit'].sum()) if len(losses) > 0 else 0
        pf = gp / gl if gl > 0 else 0
        avg_w = wins['profit'].mean() if len(wins) > 0 else 0
        avg_l = losses['profit'].mean() if len(losses) > 0 else 0
    else:
        wr = pf = avg_w = avg_l = 0

    for t in engine.closed_trades:
        t['entry_time'] = t['entry_time'].strftime('%Y-%m-%d %H:%M:%S')
        t['close_time'] = t['close_time'].strftime('%Y-%m-%d %H:%M:%S')

    result = {
        'strategy': name,
        'tf': tf,
        'params': {k: v for k, v in strat.__dict__.items() if not k.startswith('_')},
        'portfolio': port,
        'trades_summary': {
            'total': trades,
            'win_rate': round(wr, 1),
            'profit_factor': round(pf, 3),
            'net_profit': round(port.get('net_profit', 0), 2),
            'avg_win': round(avg_w, 2),
            'avg_loss': round(avg_l, 2),
        },
        'recent_trades': engine.closed_trades[-200:]
    }

    # Save
    results_file = os.path.join(RESULTS_DIR, f'single_{name}.json')
    with open(results_file, 'w') as f:
        json.dump(result, f, indent=2, cls=NumpyEncoder)
    logger.info(f"Results saved to {results_file}")

    print(f"\n{'='*60}")
    print(f"  {name} (tf={tf})")
    print(f"  Params: {result['params']}")
    print(f"{'='*60}")
    print(f"  Trades:      {trades}")
    print(f"  Net P&L:     ${result['trades_summary']['net_profit']:>8.2f}")
    print(f"  Win Rate:    {wr:>5.1f}%")
    print(f"  Profit Fact: {pf:>6.3f}")
    print(f"  Avg Win:     ${avg_w:>8.2f}")
    print(f"  Avg Loss:    ${avg_l:>8.2f}")
    mrets = port.get('monthly_returns', {})
    if mrets:
        print(f"  Max DD:      {port.get('max_drawdown', 0):>5.2f}%")
        print(f"  Return:      {port.get('total_return', 0):>5.2f}%")
        active = {k: v for k, v in mrets.items() if v != 0}
        if active:
            print(f"  Months:      {dict(list(active.items())[:6])}...")
    print(f"{'='*60}\n")
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('strategy', help='Strategy class name (e.g. SuperTrendEMA)')
    parser.add_argument('--label', help='Override strategy name for TF lookup')
    args = parser.parse_args()

    # Dynamically import
    for fname in os.listdir(STRATEGY_DIR):
        if fname.endswith('.py') and not fname.startswith('_'):
            modname = fname[:-3]
            modpath = f'strategies.{modname}'
            try:
                mod = importlib.import_module(modpath)
                if hasattr(mod, args.strategy):
                    cls = getattr(mod, args.strategy)
                    run_single(cls, label=args.label)
                    sys.exit(0)
            except Exception:
                continue
    print(f"Strategy class '{args.strategy}' not found")
    sys.exit(1)
