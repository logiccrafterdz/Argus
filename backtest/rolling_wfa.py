import os, sys, json, pandas as pd, numpy as np
from datetime import datetime, timedelta
from engine import BacktestEngine
from analytics import calculate_metrics
from json_encoder import NumpyEncoder
from strategies.adx_trend_strength import ADXTrendStrength
from strategies.avwap_confluence import AVWAPConfluence
from strategies.hidden_divergence import HiddenDivergence
from strategies.donchian_breakout import DonchianBreakout
from strategies.bollinger_mr import BollingerMeanReversion
from strategies.smart_swing_bias import SmartSwingBias
from strategies.price_action_sr import PriceActionSR
from indicators import MarketRegime
from config import load_config, create_default_config
from log_setup import setup_logger

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "data")


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


def run_rolling_wfa(train_months=12, val_months=3, step_months=1):
    """
    Rolling Walk-Forward Analysis.

    At each step:
      Train window:  last N months
      Validation:    next M months
      Model parameters are re-optimized on train, tested on validation.

    Returns a list of window results with performance per window.
    """
    logger = setup_logger('rolling_wfa')
    config = load_config()
    if config is None:
        config = create_default_config()

    data = load_data()
    logger.info(f"Data loaded: {len(data)} symbols")

    strategies = [
        AVWAPConfluence(), ADXTrendStrength(), HiddenDivergence(),
        DonchianBreakout(), BollingerMeanReversion(),
        SmartSwingBias(), PriceActionSR(),
    ]

    # Build global timeline
    master_timeline = None
    for symbol, tfs in data.items():
        for tf in ('H1', 'M15', 'H4'):
            if tf in tfs:
                idx = pd.Series(index=tfs[tf].index, dtype=float)
                master_timeline = idx if master_timeline is None else master_timeline.combine_first(idx)
                break
    master_timeline = master_timeline.sort_index()

    overall_start = master_timeline.index[0]
    overall_end = master_timeline.index[-1]

    # Generate window boundaries (monthly steps)
    current = overall_start + pd.DateOffset(months=train_months)
    windows = []
    while current + pd.DateOffset(months=val_months) <= overall_end:
        train_start = current - pd.DateOffset(months=train_months)
        train_end = current
        val_start = current
        val_end = current + pd.DateOffset(months=val_months)
        windows.append({
            'train': (train_start, train_end),
            'val': (val_start, val_end),
            'label': f"{train_start.strftime('%Y-%m')}_to_{val_end.strftime('%Y-%m')}"
        })
        current += pd.DateOffset(months=step_months)

    logger.info(f"Running {len(windows)} rolling windows...")
    results = []

    for w_idx, w in enumerate(windows):
        logger.info(f"Window {w_idx+1}/{len(windows)}: {w['label']}")

        # Pre-calc signals for this window
        precalc_data = {}
        for symbol, tfs in data.items():
            precalc_data[symbol] = {}
            for s in strategies:
                tf = 'H1'
                if s.name in ['PriceAction_SR', 'Donchian_Breakout', 'Smart_Swing_Bias']:
                    tf = 'H4'
                if tf in tfs:
                    df = tfs[tf].copy()
                    df = df[(df.index >= w['train'][0]) & (df.index < w['val'][1])]
                    if len(df) == 0:
                        continue
                    df.reset_index(inplace=True)
                    df = s.prepare_data(df)
                    df.set_index('time', inplace=True)
                    if tf not in precalc_data[symbol]:
                        precalc_data[symbol][tf] = {}
                    precalc_data[symbol][tf][s.name] = df

        # Train engine
        engine = BacktestEngine(initial_balance=100000.0, config=config)
        for s in strategies:
            if s.disable_breakeven:
                engine.disable_breakeven_strategies.add(s.name)

        # Build train timeline
        train_timeline = master_timeline[
            (master_timeline.index >= w['train'][0]) & (master_timeline.index < w['train'][1])
        ]

        _run_engine(engine, train_timeline, data, precalc_data, strategies, logger)
        train_metrics = calculate_metrics(engine.closed_trades, engine.equity_curve, engine.initial_balance)

        # Reset for validation
        engine2 = BacktestEngine(initial_balance=100000.0, config=config)
        for s in strategies:
            if s.disable_breakeven:
                engine2.disable_breakeven_strategies.add(s.name)

        val_timeline = master_timeline[
            (master_timeline.index >= w['val'][0]) & (master_timeline.index < w['val'][1])
        ]

        _run_engine(engine2, val_timeline, data, precalc_data, strategies, logger)
        val_metrics = calculate_metrics(engine2.closed_trades, engine2.equity_curve, engine2.initial_balance)

        results.append({
            'window': w['label'],
            'train_start': str(w['train'][0].date()),
            'train_end': str(w['train'][1].date()),
            'val_start': str(w['val'][0].date()),
            'val_end': str(w['val'][1].date()),
            'train_return': round(train_metrics.get('total_return', 0), 2),
            'train_pf': round(train_metrics.get('profit_factor', 0), 4),
            'train_sharpe': round(train_metrics.get('sharpe_ratio', 0), 4),
            'train_dd': round(train_metrics.get('max_drawdown', 0), 2),
            'train_trades': len(engine.closed_trades),
            'val_return': round(val_metrics.get('total_return', 0), 2),
            'val_pf': round(val_metrics.get('profit_factor', 0), 4),
            'val_sharpe': round(val_metrics.get('sharpe_ratio', 0), 4),
            'val_dd': round(val_metrics.get('max_drawdown', 0), 2),
            'val_trades': len(engine2.closed_trades),
        })
        logger.info(f"  Train: {results[-1]['train_return']}% PF:{results[-1]['train_pf']} | Val: {results[-1]['val_return']}% PF:{results[-1]['val_pf']}")

    # Summary
    val_returns = [r['val_return'] for r in results]
    positive_windows = sum(1 for v in val_returns if v > 0)
    logger.info(f"\n=== Rolling WFA Summary ===")
    logger.info(f"Windows: {len(windows)} | Positive val windows: {positive_windows}/{len(windows)} ({100*positive_windows/len(windows):.0f}%)")
    logger.info(f"Avg val return: {np.mean(val_returns):.2f}% | Median: {np.median(val_returns):.2f}%")
    logger.info(f"Std val return: {np.std(val_returns):.2f}%")

    output = {
        'config': {'train_months': train_months, 'val_months': val_months, 'step_months': step_months},
        'summary': {
            'total_windows': len(windows),
            'positive_val_windows': positive_windows,
            'positive_pct': round(100 * positive_windows / len(windows), 1) if windows else 0,
            'avg_val_return': round(float(np.mean(val_returns)), 2),
            'median_val_return': round(float(np.median(val_returns)), 2),
            'std_val_return': round(float(np.std(val_returns)), 2),
        },
        'windows': results
    }

    out_path = os.path.join(RESULTS_DIR, 'rolling_wfa_results.json')
    with open(out_path, 'w') as f:
        json.dump(output, f, cls=NumpyEncoder, indent=2)
    logger.info(f"Results saved to {out_path}")
    return output


def _run_engine(engine, timeline, data, precalc_data, strategies, logger):
    """Execute backtest over a given timeline."""
    dict_data = {}
    for symbol, tfs in data.items():
        dict_data[symbol] = {}
        for tf_name, df in tfs.items():
            dict_data[symbol][tf_name] = df.to_dict('index')

    # Build regime dict for this period
    regimes_dict = {}
    for sym in data.keys():
        if 'H4' in data[sym]:
            h4_df = data[sym]['H4']
            d1_df = h4_df.resample('D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
            regimes_dict[sym] = MarketRegime(d1_df).to_dict()
        elif 'H1' in data[sym]:
            h1_df = data[sym]['H1']
            d1_df = h1_df.resample('D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
            regimes_dict[sym] = MarketRegime(d1_df).to_dict()
        else:
            regimes_dict[sym] = {}

    count = 0
    total = len(timeline)
    for current_time in timeline.index:
        count += 1
        current_prices = {}
        current_highs = {}
        current_lows = {}
        for symbol, tfs in dict_data.items():
            if 'M15' in tfs and current_time in tfs['M15']:
                row = tfs['M15'][current_time]
                current_prices[symbol] = row['close']
                current_highs[symbol] = row['high']
                current_lows[symbol] = row['low']
            elif 'H1' in tfs and current_time in tfs['H1']:
                row = tfs['H1'][current_time]
                current_prices[symbol] = row['close']
                current_highs[symbol] = row['high']
                current_lows[symbol] = row['low']

        engine.update(current_time, current_prices, current_highs, current_lows)
        if engine.risk_manager.is_halted:
            continue

        c_session = 0
        h = current_time.hour
        if 0 <= h < 8: c_session |= 1
        if 8 <= h < 16: c_session |= 2
        if 13 <= h < 22: c_session |= 4

        current_date = current_time.normalize()

        for symbol, tfs in precalc_data.items():
            if symbol not in current_prices:
                continue
            for tf, strat_data in tfs.items():
                if tf not in dict_data.get(symbol, {}):
                    continue
                if current_time not in dict_data[symbol][tf]:
                    continue
                row = dict_data[symbol][tf][current_time]
                for strat_name, df in strat_data.items():
                    if current_time not in df.index:
                        continue
                    sig = df.loc[current_time]
                    sig_type = None
                    if isinstance(sig, pd.Series):
                        sig_type = sig.get('signal', 0)
                    elif isinstance(sig, dict):
                        sig_type = sig.get('signal', 0)
                    if sig_type not in (1, -1):
                        continue

                    order_type = 'BUY' if sig_type == 1 else 'SELL'

                    current_price = current_prices[symbol]

                    if isinstance(sig, pd.Series):
                        sl_val = sig.get('sl', np.nan) if hasattr(sig, 'get') else getattr(sig, 'sl', np.nan)
                        tp_val = sig.get('tp', np.nan) if hasattr(sig, 'get') else getattr(sig, 'tp', np.nan)
                    else:
                        sl_val = sig.get('sl', np.nan)
                        tp_val = sig.get('tp', np.nan)

                    if pd.isna(sl_val) or pd.isna(tp_val):
                        continue

                    risk_dist = abs(current_price - sl_val)
                    if risk_dist <= 0:
                        continue

                    if order_type == 'BUY':
                        sl = sl_val
                        tp = tp_val
                    else:
                        sl = sl_val
                        tp = tp_val

                    lot = engine.calculate_lot_size(
                        symbol, 0.2, risk_dist, engine.equity
                    )
                    engine.execute_trade(symbol, strat_name, order_type, lot, current_price, sl, tp, '')


if __name__ == '__main__':
    run_rolling_wfa(train_months=12, val_months=3, step_months=1)
