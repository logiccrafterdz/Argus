import os
import pandas as pd
import json
import sys
from engine import BacktestEngine
from analytics import calculate_metrics
import numpy as np
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

def run_oos(mode):
    logger = setup_logger('oos_' + mode)
    config = load_config()
    if config is None:
        config = create_default_config()

    logger.info("Loading historical data...")
    data = load_data()
    logger.info(f"Data loaded: {len(data)} symbols")

    engine = BacktestEngine(
        initial_balance=config.get('backtest', {}).get('initial_balance', 100000.0),
        config=config
    )

    strategies = [
        AVWAPConfluence(),
        ADXTrendStrength(),
        HiddenDivergence(),
        DonchianBreakout(),
        BollingerMeanReversion(),
        SmartSwingBias(),
        PriceActionSR(),
    ]

    for strat in strategies:
        if strat.disable_breakeven:
            engine.disable_breakeven_strategies.add(strat.name)

    master_timeline = None
    for symbol, tfs in data.items():
        if 'M15' in tfs:
            idx = pd.Series(index=tfs['M15'].index, dtype=float)
        elif 'H1' in tfs:
            idx = pd.Series(index=tfs['H1'].index, dtype=float)
        else:
            continue
        if master_timeline is None:
            master_timeline = idx
        else:
            master_timeline = master_timeline.combine_first(idx)

    master_timeline = master_timeline.sort_index()

    # Split by period
    if mode == 'train':
        master_timeline = master_timeline[master_timeline.index < '2024-01-01']
        logger.info("TRAIN period: Jan 2022 - Dec 2023")
    else:
        master_timeline = master_timeline[master_timeline.index >= '2024-01-01']
        logger.info("TEST period: Jan 2024 - May 2025")

    logger.info("Pre-calculating strategy signals...")
    precalc_data = {}
    for symbol, tfs in data.items():
        precalc_data[symbol] = {}
        for strat_idx, strat in enumerate(strategies):
            logger.info(f"Processing {symbol} - {strat.name}")
            tf = 'H1'
            if strat.name in ['ICT_Killzone_Macro', 'ORB_Session', 'ORB_Hybrid', 'Asian_Range_Fakeout', 'NY_Session_Reversal', 'PDH_PDL_BreakReversal']:
                tf = 'M15'
            elif strat.name in ['PriceAction_SR', 'Donchian_Breakout', 'Smart_Swing_Bias']:
                tf = 'H4'

            if tf in tfs:
                df = tfs[tf].copy()
                df.reset_index(inplace=True)
                df = strat.prepare_data(df)
                df.set_index('time', inplace=True)
                # Filter to same period
                if mode == 'train':
                    df = df[df.index < '2024-01-01']
                else:
                    df = df[df.index >= '2024-01-01']
                if tf not in precalc_data[symbol]:
                    precalc_data[symbol][tf] = {}
                precalc_data[symbol][tf][strat.name] = df

    logger.info("Building regime dict per symbol...")
    regimes_dict = {}
    for sym in data.keys():
        if 'H4' in data[sym]:
            h4_df = data[sym]['H4']
            if mode == 'train':
                h4_df = h4_df[h4_df.index < '2024-01-01']
            else:
                h4_df = h4_df[h4_df.index >= '2024-01-01']
            if len(h4_df) < 20:
                regimes_dict[sym] = {}
                continue
            d1_df = h4_df.resample('D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
            m_regime = MarketRegime(d1_df)
            regimes_dict[sym] = m_regime.to_dict()
        elif 'H1' in data[sym]:
            h1_df = data[sym]['H1']
            if mode == 'train':
                h1_df = h1_df[h1_df.index < '2024-01-01']
            else:
                h1_df = h1_df[h1_df.index >= '2024-01-01']
            if len(h1_df) < 20:
                regimes_dict[sym] = {}
                continue
            d1_df = h1_df.resample('D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
            m_regime = MarketRegime(d1_df)
            regimes_dict[sym] = m_regime.to_dict()
        else:
            regimes_dict[sym] = {}

    logger.info("Building correlation matrix...")
    all_symbols = list(data.keys())
    h1_closes = {}
    for sym in all_symbols:
        if 'H1' in data[sym]:
            h1_df = data[sym]['H1']
            if mode == 'train':
                h1_df = h1_df[h1_df.index < '2024-01-01']
            else:
                h1_df = h1_df[h1_df.index >= '2024-01-01']
            h1_closes[sym] = h1_df['close']
    corr_df = pd.DataFrame(h1_closes)
    corr_matrix = corr_df.corr()
    logger.info(f"Correlation matrix built for {len(corr_matrix.columns)} symbols.")

    logger.info("Converting historical data to fast dict lookups...")
    dict_data = {}
    for symbol, tfs in data.items():
        dict_data[symbol] = {}
        for tf_name, df in tfs.items():
            if mode == 'train':
                df = df[df.index < '2024-01-01']
            else:
                df = df[df.index >= '2024-01-01']
            dict_data[symbol][tf_name] = df.to_dict('index')

    logger.info("Converting strategy precalculated data to fast dict lookups...")
    dict_precalc = {}
    for symbol, tfs in precalc_data.items():
        dict_precalc[symbol] = {}
        for tf, strat_data in tfs.items():
            dict_precalc[symbol][tf] = {}
            for strat_name, df in strat_data.items():
                dict_precalc[symbol][tf][strat_name] = df.to_dict('index')

    logger.info(f"Executing backtest over {len(master_timeline)} bars...")
    count = 0
    total = len(master_timeline)
    for current_time in master_timeline.index:
        count += 1
        if count % 5000 == 0:
            logger.info(f"Progress: {count}/{total}")

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

        current_date = current_time.normalize()

        c_session = 0
        h = current_time.hour
        if 0 <= h < 8: c_session |= 1
        if 8 <= h < 16: c_session |= 2
        if 13 <= h < 22: c_session |= 4

        engine.update(current_time, current_prices, current_highs, current_lows)

        if engine.risk_manager.is_halted:
            continue

        for symbol, tfs in dict_precalc.items():
            if symbol not in current_prices:
                continue
            for tf, strat_data in tfs.items():
                if tf == 'M15':
                    if 'M15' not in dict_data[symbol] or current_time not in dict_data[symbol]['M15']: continue
                elif tf == 'H1':
                    if current_time.minute != 0: continue
                    if 'H1' not in dict_data[symbol] or current_time not in dict_data[symbol]['H1']: continue
                elif tf == 'H4':
                    if current_time.minute != 0 or current_time.hour % 4 != 0: continue
                    if 'H4' not in dict_data[symbol] or current_time not in dict_data[symbol]['H4']: continue

                for strat in strategies:
                    if strat.name not in strat_data: continue
                    sym_regime_dict = regimes_dict.get(symbol, {})
                    c_regime = sym_regime_dict.get(current_date, 1)
                    if not strat.check_regime(c_regime) or not strat.check_session(c_session): continue
                    if current_time in strat_data[strat.name]:
                        row = strat_data[strat.name][current_time]
                    else:
                        continue
                    if row['signal'] == 1:
                        risk_dist = current_prices[symbol] - row['sl']
                        if risk_dist <= 0 or pd.isna(risk_dist): continue
                        if not engine.risk_manager.check_correlation(symbol, 'BUY', engine.open_positions, corr_matrix, 0.8): continue
                        lot = engine.calculate_lot_size(symbol, 0.2, risk_dist, engine.equity)
                        engine.execute_trade(symbol, strat.name, 'BUY', lot, current_prices[symbol], row['sl'], row['tp'], "Buy Signal")
                    elif row['signal'] == -1:
                        risk_dist = row['sl'] - current_prices[symbol]
                        if risk_dist <= 0 or pd.isna(risk_dist): continue
                        if not engine.risk_manager.check_correlation(symbol, 'SELL', engine.open_positions, corr_matrix, 0.8): continue
                        lot = engine.calculate_lot_size(symbol, 0.2, risk_dist, engine.equity)
                        engine.execute_trade(symbol, strat.name, 'SELL', lot, current_prices[symbol], row['sl'], row['tp'], "Sell Signal")

    engine.emergency_close_all(current_prices)

    logger.info("Backtest finished. Calculating metrics...")
    port_metrics = calculate_metrics(engine.closed_trades, engine.equity_curve, 100000.0)

    for point in engine.equity_curve:
        point['date'] = point['date'].strftime('%Y-%m-%d')
    for t in engine.closed_trades:
        t['entry_time'] = t['entry_time'].strftime('%Y-%m-%d %H:%M:%S')
        t['close_time'] = t['close_time'].strftime('%Y-%m-%d %H:%M:%S')

    results = {
        'mode': mode,
        'portfolio': port_metrics,
        'equity_curve': engine.equity_curve,
        'recent_trades': engine.closed_trades[-100:],
        'total_trades': len(engine.closed_trades),
    }

    abs_results_dir = os.path.abspath(RESULTS_DIR)
    if not os.path.exists(abs_results_dir):
        os.makedirs(abs_results_dir)

    out_path = os.path.join(abs_results_dir, f'oos_{mode}.json')
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=4, cls=NumpyEncoder)

    logger.info(f"Results saved to {out_path}")
    logger.info(f"OOS {mode} metrics: {port_metrics}")
    print(f"\n========== OOS {mode.upper()} ==========")
    print(f"Return: {port_metrics.get('total_return', 'N/A'):>7.2f}%")
    print(f"Net Profit: ${port_metrics.get('net_profit', 0):>8.2f}")
    print(f"Trades: {port_metrics.get('total_trades', 0)}")
    print(f"Win Rate: {port_metrics.get('win_rate', 0):.2f}%")
    print(f"Profit Factor: {port_metrics.get('profit_factor', 0):.2f}")
    print(f"Max DD: {port_metrics.get('max_drawdown', 0):.2f}%")
    print(f"Sharpe: {port_metrics.get('sharpe_ratio', 0):.2f}")
    print(f"Expectancy: ${port_metrics.get('expectancy', 0):.2f}")
    print(f"====================================\n")

    return port_metrics

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if mode == 'all':
        train_metrics = run_oos('train')
        test_metrics = run_oos('test')
        print("\n\n========== OOS COMPARISON ==========")
        print(f"{'Metric':<20} {'TRAIN (2022-2023)':<20} {'TEST (2024-2025)':<20}")
        print("-" * 60)
        for k in ['total_return', 'net_profit', 'total_trades', 'win_rate', 'profit_factor', 'max_drawdown', 'sharpe_ratio', 'expectancy']:
            tv = train_metrics.get(k, 0)
            tsv = test_metrics.get(k, 0)
            if k in ('net_profit', 'expectancy'):
                print(f"{k:<20} ${tv:<10.2f}        ${tsv:<10.2f}")
            elif k in ('total_return', 'win_rate', 'max_drawdown'):
                print(f"{k:<20} {tv:<10.2f}%        {tsv:<10.2f}%")
            else:
                print(f"{k:<20} {tv:<20.2f} {tsv:<20.2f}")
    else:
        run_oos(mode)
