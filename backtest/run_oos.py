import os
import sys
import time
import hashlib
import inspect
import pickle
import pandas as pd
import numpy as np
import json
from engine import BacktestEngine
from analytics import calculate_metrics
from json_encoder import NumpyEncoder
from indicators import MarketRegime
from config import load_config, create_default_config
from log_setup import setup_logger
from allocator import InstitutionalAllocator
from concurrent.futures import ThreadPoolExecutor, as_completed

from strategies.avwap_confluence import AVWAPConfluence
from strategies.trend_pullback import TrendPullback
from strategies.bollinger_mr import BollingerMeanReversion
from strategies.hidden_divergence import HiddenDivergence
from strategies.smart_swing_bias import SmartSwingBias
from strategies.price_action_sr import PriceActionSR
from strategies.volatility_squeeze import VolatilitySqueeze
from strategies.asian_range_fakeout import AsianRangeFakeout
from strategies.ny_session_reversal import NYSessionReversal
from strategies.liq_sweep_breakout import LiquiditySweepBreakout
from strategies.supertrend_ema import SuperTrendEMA

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "data")

SPLITS = {
    'train':      {'start': '2018-01-01', 'end': '2023-01-01', 'label': 'TRAIN (5 years: 2018-2022)'},
    'validation': {'start': '2023-01-01', 'end': '2024-01-01', 'label': 'VAL (1 year: 2023)'},
    'test':       {'start': '2024-01-01', 'end': '2026-06-01', 'label': 'TEST (29 mo: 2024-May 2026)'},
}

STRATEGIES = [
    AVWAPConfluence(), TrendPullback(), BollingerMeanReversion(),
    HiddenDivergence(), SmartSwingBias(), PriceActionSR(),
    VolatilitySqueeze(), AsianRangeFakeout(), NYSessionReversal(),
    LiquiditySweepBreakout(), SuperTrendEMA(),
]


def load_data():
    symbols_data = {}
    for filename in sorted(os.listdir(DATA_DIR)):
        if not filename.endswith(".csv"):
            continue
        parts = filename.split('.')[0].split('_')
        symbol = parts[0]
        tf = '_'.join(parts[1:])
        df = pd.read_csv(os.path.join(DATA_DIR, filename), parse_dates=['time'])
        df = df[(df['time'] >= '2018-01-01') & (df['time'] <= '2025-06-01')]
        if len(df) < 500:
            continue
        df.set_index('time', inplace=True)
        if symbol not in symbols_data:
            symbols_data[symbol] = {}
        symbols_data[symbol][tf] = df
    return symbols_data


def _session_from_timestamp(ts):
    h = ts.hour
    s = 0
    if 0 <= h < 8: s |= 1
    if 8 <= h < 16: s |= 2
    if 13 <= h < 22: s |= 4
    return s


def _compute_strategy_signals(args):
    strat, data_items, regimes_dict, cache_file = args
    if cache_file and os.path.exists(cache_file):
        with open(cache_file, 'rb') as _f:
            return pickle.load(_f)
    M15_STRATS = {'ICT_Killzone_Macro', 'ORB_Session', 'ORB_Hybrid',
                  'Asian_Range_Fakeout', 'NY_Session_Reversal', 'PDH_PDL_BreakReversal'}
    H4_STRATS = {'PriceAction_SR', 'Donchian_Breakout', 'Smart_Swing_Bias'}
    if strat.name in M15_STRATS: tf = 'M15'
    elif strat.name in H4_STRATS: tf = 'H4'
    else: tf = 'H1'
    local_results = []
    for symbol, tfs in data_items:
        if tf not in tfs: continue
        df = tfs[tf].copy()
        df.reset_index(inplace=True)
        df = strat.prepare_data(df)
        sig_col = df['signal'].values
        sig_idx = np.where(sig_col != 0)[0]
        if len(sig_idx) == 0: continue
        regimes_sym = regimes_dict.get(symbol, {})
        records = df.to_dict('records')
        for i in sig_idx:
            r = records[int(i)]
            ts = r['time']
            if not strat.check_regime(regimes_sym.get(ts.normalize(), 1)): continue
            if not strat.check_session(_session_from_timestamp(ts)): continue
            sl_price = r.get('sl', None)
            if sl_price is None or sl_price == 0 or abs(r['close'] - sl_price) <= 0: continue
            local_results.append((ts, {
                'symbol': symbol, 'strategy': strat.name,
                'strategy_type': strat.strategy_type,
                'order_type': 'BUY' if r['signal'] == 1 else 'SELL',
                'entry_price': r['close'], 'atr_value': r.get('atr', 0),
                'conviction': r.get('conviction', 0.5),
            }))
    if cache_file:
        try:
            with open(cache_file, 'wb') as _f:
                pickle.dump(local_results, _f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception: pass
    return local_results


def _compute_strategy_cache_key(strat, data):
    h = hashlib.md5()
    try:
        src = inspect.getsource(type(strat))
        h.update(src.encode('utf-8', errors='ignore'))
    except Exception: h.update(strat.name.encode())
    for sym in sorted(data.keys()):
        h.update(sym.encode())
        for tf in sorted(data[sym].keys()):
            df = data[sym][tf]
            if not df.empty:
                h.update(f"{tf}:{len(df)}:{df.index[0]}:{df.index[-1]}".encode())
    return h.hexdigest()[:12]


def save_oos_split(engine, closed_trades, mode, out_dir):
    p = calculate_metrics(closed_trades, engine.equity_curve, 100000.0)
    s = SPLITS[mode]
    split_start = pd.Timestamp(s['start'])
    split_end = pd.Timestamp(s['end'])
    # Filter equity curve to this split's date range
    all_eq = list(engine.equity_curve)
    split_eq = [pt for pt in all_eq if split_start <= pd.Timestamp(pt['date']) < split_end]
    # Calculate per-split metrics using only this split's equity and trades
    p = calculate_metrics(closed_trades, split_eq, 100000.0) if split_eq else calculate_metrics(closed_trades, all_eq, 100000.0)
    eq_curve = list(split_eq) if split_eq else list(all_eq)
    for pt in eq_curve:
        if hasattr(pt['date'], 'strftime'):
            pt['date'] = pt['date'].strftime('%Y-%m-%d %H:%M:%S')
    for t in closed_trades:
        t['entry_time'] = t['entry_time'].strftime('%Y-%m-%d %H:%M:%S')
        t['close_time'] = t['close_time'].strftime('%Y-%m-%d %H:%M:%S')
    for k, v in p.items():
        if hasattr(v, 'item'): p[k] = v.item()
    results = {
        'mode': mode,
        'portfolio': p,
        'equity_curve': eq_curve,
        'all_trades': closed_trades,
        'recent_trades': closed_trades[-100:],
        'total_trades': len(closed_trades),
    }
    out_path = os.path.join(out_dir, f'oos_{mode}.json')
    os.makedirs(out_dir, exist_ok=True)
    import sys as _sys
    print(f"  DEBUG: mode={mode} out_path={out_path} eq_len={len(eq_curve)} trades_len={len(closed_trades)}", file=_sys.stderr)
    try:
        with open(out_path, 'w') as f:
            json.dump(results, f, indent=4, cls=NumpyEncoder)
    except OSError as _e:
        print(f"  DEBUG OSError: {_e}", file=_sys.stderr)
        # Try writing to a temp file instead
        tmp = out_path + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(results, f, indent=4, cls=NumpyEncoder)
        import shutil
        shutil.move(tmp, out_path)
    setup_logger('oos_main').info(f"Saved {out_path}: PF={p.get('profit_factor')}, Net=${p.get('net_profit')}, Trades={p.get('total_trades')}")


def run_continuous_oos():
    np.random.seed(42)
    logger = setup_logger('oos_main')
    config = load_config() or create_default_config()

    data = load_data()
    logger.info(f"Data: {len(data)} symbols")

    engine = BacktestEngine(initial_balance=100000.0, config=config)

    # Full timeline
    master = None
    for sym, tfs in data.items():
        tf = 'M15' if 'M15' in tfs else ('H1' if 'H1' in tfs else None)
        if tf is None: continue
        idx = pd.Series(index=tfs[tf].index, dtype=float)
        master = idx if master is None else master.combine_first(idx)
    master = master.sort_index()

    # Regime dict
    regimes = {}
    for sym in data:
        for tf in ('H4', 'H1'):
            if tf in data[sym]:
                d1 = data[sym][tf].resample('D').agg({'open':'first','high':'max','low':'min','close':'last'}).dropna()
                regimes[sym] = MarketRegime(d1).to_dict()
                break
        if sym not in regimes: regimes[sym] = {}

    # Signal pre-calc
    CACHE_DIR = os.path.join(os.path.dirname(__file__), '.signal_cache')
    os.makedirs(CACHE_DIR, exist_ok=True)
    data_items = list(data.items())
    work_args = []
    for s in STRATEGIES:
        key = _compute_strategy_cache_key(s, data)
        work_args.append((s, data_items, regimes, os.path.join(CACHE_DIR, f'{s.name}_{key}.pkl')))

    signals = {}
    with ThreadPoolExecutor(max_workers=min(len(STRATEGIES), 8)) as ex:
        fs = {ex.submit(_compute_strategy_signals, a): a[0].name for a in work_args}
        for f in as_completed(fs):
            for ts, sig in f.result():
                signals.setdefault(ts, []).append(sig)
    logger.info(f"Signals: {len(signals)} bars")

    # Price lookup
    prices_lookup = {}
    for sym, tfs in data.items():
        tf = 'M15' if 'M15' in tfs else ('H1' if 'H1' in tfs else None)
        if tf is None: continue
        df = tfs[tf]
        for i, ts in enumerate(df.index):
            prices_lookup.setdefault(ts, {})[sym] = (df['close'].values[i], df['high'].values[i], df['low'].values[i])

    # Corr matrix
    h1c = {}
    for sym in data:
        if 'H1' in data[sym]: h1c[sym] = data[sym]['H1']['close']
    corr = pd.DataFrame(h1c).corr()

    alloc = InstitutionalAllocator(config)
    alloc.set_corr_matrix(corr)

    daily_ctx = {}
    for d in sorted(set(ts.normalize() for ts in master.index)):
        daily_ctx[d] = regimes.get('EURUSD', {}).get(d, 1)

    # Run continuous backtest, saving at split boundaries
    total = len(master)
    lk_prices, lk_highs, lk_lows = {}, {}, {}
    dse = None
    proc = 0
    trade_offset = 0  # track how many trades already saved

    saved_modes = set()

    for count, ct in enumerate(master.index, 1):
        if count % 10000 == 0: logger.info(f"Progress: {count}/{total}")

        # Check split boundaries and save BEFORE starting a new period
        for m in ('train', 'validation', 'test'):
            if m not in saved_modes and ct >= pd.Timestamp(SPLITS[m]['end']):
                saved_modes.add(m)
                # Save only trades that closed in this split (from trade_offset to current)
                new_trades = list(engine.closed_trades[trade_offset:])
                trade_offset = len(engine.closed_trades)
                # Equity curve is cumulative from engine start — correct for chained OOS
                save_oos_split(engine, new_trades, m, RESULTS_DIR)
                logger.info(f"Saved split {m}: {len(new_trades)} new trades")

        # Price lookup etc...
        row = prices_lookup.get(ct, {})
        cp, ch, cl = {}, {}, {}
        for s, (c, h, lo) in row.items():
            cp[s] = c; ch[s] = h; cl[s] = lo
            lk_prices[s] = c; lk_highs[s] = h; lk_lows[s] = lo
        for s in lk_prices:
            if s not in cp: cp[s] = lk_prices[s]; ch[s] = lk_highs[s]; cl[s] = lk_lows[s]

        cd = ct.normalize()
        if dse is None or cd != getattr(engine, '_last_be_date', None):
            dse = engine.equity
            engine._last_be_date = cd

        engine.update(ct, cp, ch, cl)
        alloc.reset_daily(cd, engine.balance, engine.peak_balance)

        if dse > 0 and engine.equity >= dse * 1.02:
            for pos in engine.open_positions:
                sp = engine.spread_map.get(pos['symbol'], engine.default_spread)
                if pos['type'] == 'BUY' and pos['sl'] < pos['entry_price']:
                    pos['sl'] = pos['entry_price'] + sp
                elif pos['type'] == 'SELL' and pos['sl'] > pos['entry_price']:
                    pos['sl'] = pos['entry_price'] - sp

        if engine.risk_manager.is_halted: continue

        raw = signals.get(ct, [])
        if raw:
            try:
                thr = alloc.throttle_multiplier()
                approved = alloc.filter(raw, open_positions=engine.open_positions, current_regime=daily_ctx.get(cd, 1)) if thr > 0 else []
            except Exception as e:
                logger.error(f"Alloc err at {ct}: {e}")
                approved = []
        else:
            approved = []

        for sig in approved:
            if sig['symbol'] not in cp: continue
            apct = sig.get('allocated_risk_pct', 0.02) * thr
            rpct = apct * 100.0
            stv = sig['strategy_type'].value if hasattr(sig['strategy_type'], 'value') else sig['strategy_type']
            ep = sig['entry_price']
            av = sig['atr_value']
            slm = {'trend_momentum': 2.0, 'mean_reversion': 1.0, 'stop_hunt': 0.5}.get(stv, 2.0)
            slp = ep - slm * av if sig['order_type'] == 'BUY' else ep + slm * av
            rd = abs(cp[sig['symbol']] - slp)
            if rd <= 0: continue
            ls = engine.calculate_lot_size(sig['symbol'], rpct, rd, engine.equity)
            if ls <= 0: continue
            engine.execute_trade(
                symbol=sig['symbol'], strategy_name=sig['strategy'],
                strategy_type=sig['strategy_type'], order_type=sig['order_type'],
                lot_size=ls, entry_price=ep, atr_value=av,
                comment=f"{sig['strategy']}_{sig['symbol']}_{ct.date()}",
            )

        if engine.is_bankrupt:
            logger.warning(f"Bankrupt at {ct}")
            break

    engine.emergency_close_all(cp)

    # Save remaining trades as final split (test)
    for m in ('test',):
        if m not in saved_modes:
            new_trades = list(engine.closed_trades[trade_offset:])
            save_oos_split(engine, new_trades, m, RESULTS_DIR)
            saved_modes.add(m)
            logger.info(f"Saved split {m}: {len(new_trades)} new trades")

    # Ensure all modes are saved
    for m in ('validation', 'train'):
        if m not in saved_modes:
            save_oos_split(engine, [], m, RESULTS_DIR)
            saved_modes.add(m)

    logger.info("Continuous OOS complete. Combining results...")
    combine_results()


def combine_results():
    abs_dir = os.path.abspath(RESULTS_DIR)
    splits = {}
    for mode in ['train', 'validation', 'test']:
        fp = os.path.join(abs_dir, f'oos_{mode}.json')
        if not os.path.exists(fp):
            print(f"WARNING: {fp} not found")
            continue
        with open(fp) as f:
            splits[mode] = json.load(f)

    if len(splits) < 3:
        print("Not all splits available, skipping combine")
        return

    all_trades = []
    for mode in ['train', 'validation', 'test']:
        all_trades.extend(splits[mode].get('all_trades', []))

    all_equity = []
    for mode in ['train', 'validation', 'test']:
        all_equity.extend(splits[mode].get('equity_curve', []))
    seen = set()
    merged_eq = []
    for pt in all_equity:
        if pt['date'] not in seen:
            seen.add(pt['date'])
            merged_eq.append(pt)

    pm = calculate_metrics(all_trades, merged_eq, 100000.0) if all_trades else splits['train'].get('portfolio', {})
    df = pd.DataFrame(all_trades)
    sm = []
    if not df.empty:
        for sn in sorted(df['strategy'].unique()):
            st = df[df['strategy'] == sn]
            w = st[st['profit'] > 0]
            l = st[st['profit'] <= 0]
            gp = w['profit'].sum(); gl = abs(l['profit'].sum())
            sm.append({'name': sn, 'category': '', 'total_trades': len(st),
                       'win_rate': round(len(w)/len(st)*100, 2),
                       'profit_factor': round(gp/gl, 2) if gl > 0 else float('inf'),
                       'net_profit': round(st['profit'].sum(), 2)})
    for k, v in pm.items():
        if hasattr(v, 'item'): pm[k] = v.item()
    for s in sm:
        for k, v in s.items():
            if hasattr(v, 'item'): s[k] = v.item()
    out = {'portfolio': pm, 'strategies': sm, 'equity_curve': merged_eq, 'recent_trades': all_trades[-100:]}
    fp = os.path.join(abs_dir, 'results.json')
    with open(fp, 'w') as f:
        json.dump(out, f, indent=4, cls=NumpyEncoder)
    print(f"\nCombined results saved to {fp}")
    print(f"Total trades: {len(all_trades)}, Equity: {len(merged_eq)}, PF={pm.get('profit_factor')}, Net=${pm.get('net_profit')}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if mode == 'all':
        run_continuous_oos()
    elif mode == 'combine':
        combine_results()
