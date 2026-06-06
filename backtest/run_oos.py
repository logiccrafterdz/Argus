import os
import sys
import pandas as pd
import json
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

# Optional module imports (degrade gracefully if library missing)
try:
    from indicators import HMM_AVAILABLE as _H, HMMRegimeDetector as _HMM
    HMM_REGIME_AVAILABLE = _H
except ImportError:
    HMM_REGIME_AVAILABLE = False
try:
    from sentiment import SentimentFilter
    SENTIMENT_AVAILABLE = True
except ImportError:
    SENTIMENT_AVAILABLE = False
try:
    from meta_labeling import MetaLabelingFilter
    META_AVAILABLE = True
except ImportError:
    META_AVAILABLE = False
try:
    from rl_agent import AdaptiveTPSLAgent
    RL_AVAILABLE = True
except ImportError:
    RL_AVAILABLE = False
try:
    from kelly_agent import KellyAgent
    KELLY_AVAILABLE = True
except ImportError:
    KELLY_AVAILABLE = False
try:
    from agent_system import AgentSystem
    AGENT_SYSTEM_AVAILABLE = True
except ImportError:
    AGENT_SYSTEM_AVAILABLE = False

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "data")

# Split config: ~65% train, ~15% validation, ~20% test (2018-01 to 2025-05)
SPLITS = {
    'train':      {'start': '2017-01-01', 'end': '2023-01-01', 'label': 'TRAIN (5 years: 2018-2022)'},
    'validation': {'start': '2023-01-01', 'end': '2024-01-01', 'label': 'VAL (1 year: 2023)'},
    'test':       {'start': '2024-01-01', 'end': '2026-06-01', 'label': 'TEST (29 mo: 2024-May 2026)'},
}

def load_data():
    symbols_data = {}
    for filename in sorted(os.listdir(DATA_DIR)):
        if filename.endswith(".csv"):
            symbol, tf = filename.split('.')[0].split('_')
            filepath = os.path.join(DATA_DIR, filename)
            df = pd.read_csv(filepath, parse_dates=['time'])
            df.set_index('time', inplace=True)
            if symbol not in symbols_data:
                symbols_data[symbol] = {}
            symbols_data[symbol][tf] = df
    return symbols_data

def filter_by_period(df, mode):
    s = SPLITS[mode]
    return df[(df.index >= s['start']) & (df.index < s['end'])].copy()

def run_oos(mode, existing_rl_agent=None, existing_meta_filters=None, existing_kelly_agent=None):
    np.random.seed(42)
    logger = setup_logger('oos_' + mode)
    s = SPLITS[mode]
    config = load_config()
    if config is None:
        config = create_default_config()

    logger.info("Loading historical data...")
    data = load_data()
    logger.info(f"Data loaded: {len(data)} symbols")

    # Pre-compute ATR for ATR-based slippage model
    atr_map = {}
    atr_sma_map = {}
    adx_map = {}
    for sym in data:
        for tf in ('H1', 'M15', 'H4'):
            if tf in data[sym]:
                df = data[sym][tf]
                high_low = df['high'] - df['low']
                high_close = (df['high'] - df['close'].shift()).abs()
                low_close = (df['low'] - df['close'].shift()).abs()
                tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                atr = tr.rolling(14).mean().bfill().fillna(tr)
                atr_sma = atr.rolling(20).mean().bfill().fillna(atr)
                atr_map[sym] = atr.values
                atr_sma_map[sym] = atr_sma.values
                # ADX for filter features
                up = df['high'].diff()
                down = -df['low'].diff()
                pos_dm = np.where((up > down) & (up > 0), up, 0.0)
                neg_dm = np.where((down > up) & (down > 0), down, 0.0)
                atr14 = tr.rolling(14).mean().replace(0, np.nan)
                pdi = 100 * pd.Series(pos_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr14
                ndi = 100 * pd.Series(neg_dm, index=df.index).ewm(alpha=1/14, adjust=False).mean() / atr14
                dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
                adx = dx.ewm(alpha=1/14, adjust=False).mean().bfill().fillna(25)
                adx_map[sym] = adx.values
                break

    engine = BacktestEngine(
        initial_balance=config.get('backtest', {}).get('initial_balance', 100000.0),
        config=config
    )
    engine.atr_map = atr_map

    strategies = [
        AVWAPConfluence(),
        ADXTrendStrength(),
        # HiddenDivergence(),
        DonchianBreakout(),
        # BollingerMeanReversion(),
        SmartSwingBias(),
        PriceActionSR(),
    ]

    # ===== INTEGRATIONS SETUP =====
    regime_method = config.get('regime', {}).get('method', 'adx')
    enable_sentiment = config.get('sentiment', {}).get('enabled', False) and SENTIMENT_AVAILABLE
    enable_meta = config.get('meta_labeling', {}).get('enabled', False) and META_AVAILABLE
    enable_rl = config.get('rl_agent', {}).get('enabled', False) and RL_AVAILABLE
    enable_agent_system = config.get('agent_system', {}).get('enabled', False) and AGENT_SYSTEM_AVAILABLE

    hmm_detectors = {}
    if regime_method == 'hmm' and HMM_REGIME_AVAILABLE:
        logger.info("Using HMM regime detection")

    sentiment_filter = None
    if config.get('sentiment', {}).get('enabled', False) and SENTIMENT_AVAILABLE:
        sentiment_filter = SentimentFilter()
        fg_df = data.get('EURUSD', {}).get('H1')
        if fg_df is None:
            fg_df = next((tfs['H1'] for tfs in data.values() if 'H1' in tfs), None)
        if fg_df is not None:
            sentiment_filter.feed_prices(fg_df)
        logger.info("SentimentFilter enabled")

    meta_filters = existing_meta_filters if existing_meta_filters is not None else {}
    if enable_meta and not meta_filters:
        for strat_obj in strategies:
            meta_filters[strat_obj.name] = MetaLabelingFilter(strat_obj.name)
        logger.info(f"Meta-labeling enabled for {len(strategies)} strategies")

    rl_agent = existing_rl_agent
    if enable_rl and rl_agent is None:
        rl_agent = AdaptiveTPSLAgent()
        logger.info("RL Agent (TP/SL) enabled")

    enable_kelly = config.get('kelly', {}).get('enabled', True) and KELLY_AVAILABLE
    kelly_agent = existing_kelly_agent if existing_kelly_agent is not None else (KellyAgent() if enable_kelly else None)
    if kelly_agent:
        logger.info("Kelly Agent enabled")

    agent_system = None
    if enable_agent_system:
        agent_system = AgentSystem(engine, meta_filters=meta_filters,
                                   sentiment_filter=sentiment_filter, rl_agent=rl_agent, kelly_agent=kelly_agent)
        logger.info("AgentSystem enabled")

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
    master_timeline = filter_by_period(master_timeline.to_frame(), mode)
    logger.info(f"{s['label']} — {len(master_timeline)} bars")

    logger.info("Pre-calculating strategy signals...")
    precalc_data = {}
    for symbol, tfs in data.items():
        precalc_data[symbol] = {}
        for strat in strategies:
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
                df = filter_by_period(df, mode)
                if tf not in precalc_data[symbol]:
                    precalc_data[symbol][tf] = {}
                precalc_data[symbol][tf][strat.name] = df

    logger.info("Building regime dict per symbol...")
    regimes_dict = {}
    for sym in data.keys():
        if 'H4' in data[sym]:
            h4_df = filter_by_period(data[sym]['H4'], mode)
            if len(h4_df) < 20:
                regimes_dict[sym] = {}
                continue
            d1_df = h4_df.resample('D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
            if regime_method == 'hmm' and HMM_REGIME_AVAILABLE:
                hmm_det = HMMRegimeDetector()
                hmm_det.fit(d1_df)
                regimes_dict[sym] = hmm_det.to_dict(d1_df)
            else:
                regimes_dict[sym] = MarketRegime(d1_df).to_dict()
        elif 'H1' in data[sym]:
            h1_df = filter_by_period(data[sym]['H1'], mode)
            if len(h1_df) < 20:
                regimes_dict[sym] = {}
                continue
            d1_df = h1_df.resample('D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
            if regime_method == 'hmm' and HMM_REGIME_AVAILABLE:
                hmm_det = HMMRegimeDetector()
                hmm_det.fit(d1_df)
                regimes_dict[sym] = hmm_det.to_dict(d1_df)
            else:
                regimes_dict[sym] = MarketRegime(d1_df).to_dict()
        else:
            regimes_dict[sym] = {}

    logger.info("Building correlation matrix...")
    all_symbols = list(data.keys())
    h1_closes = {}
    for sym in all_symbols:
        if 'H1' in data[sym]:
            h1_df = filter_by_period(data[sym]['H1'], mode)
            h1_closes[sym] = h1_df['close']
    corr_df = pd.DataFrame(h1_closes)
    corr_matrix = corr_df.corr()
    logger.info(f"Correlation matrix built for {len(corr_matrix.columns)} symbols.")

    logger.info("Converting historical data to fast dict lookups...")
    dict_data = {}
    for symbol, tfs in data.items():
        dict_data[symbol] = {}
        for tf_name, df in tfs.items():
            dict_data[symbol][tf_name] = filter_by_period(df, mode).to_dict('index')

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
    processed_trades = 0
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
                        direction = 'BUY'
                        risk_dist = current_prices[symbol] - row['sl']
                    elif row['signal'] == -1:
                        direction = 'SELL'
                        risk_dist = row['sl'] - current_prices[symbol]
                    else:
                        continue
                    if risk_dist <= 0 or pd.isna(risk_dist):
                        continue

                    bar_idx = min(engine.bar_index, len(adx_map.get(symbol, [25])) - 1)
                    adx_val = adx_map.get(symbol, [25.0])[bar_idx] if symbol in adx_map else 25.0
                    atr_val = atr_map.get(symbol, [0.001])[min(bar_idx, len(atr_map.get(symbol, [0.001])) - 1)]
                    atr_ratio = atr_val / (current_prices[symbol] + 1e-10)

                    # --- Sentiment Filter ---
                    if sentiment_filter and not sentiment_filter.should_trade(direction, current_time, symbol):
                        continue

                    feat = None
                    # --- Meta-Labeling Filter ---
                    if enable_meta and strat.name in meta_filters:
                        mf = meta_filters[strat.name]
                        feat = {
                            'atr_ratio': atr_ratio, 'adx': adx_val,
                            'spread': config.get('spread', {}).get(symbol, 0.0001),
                            'hour': current_time.hour, 'day_of_week': current_time.weekday(),
                            'session_asia': 1 if c_session & 1 else 0,
                            'session_london': 1 if c_session & 2 else 0,
                            'session_ny': 1 if c_session & 4 else 0,
                            'range_pct': ((current_highs.get(symbol, 0) - current_lows.get(symbol, 0)) /
                                          (current_prices[symbol] + 1e-10)),
                        }
                        if not mf.should_trade(feat):
                            continue

                    # --- Correlation Check ---
                    if not engine.risk_manager.check_correlation(symbol, direction, engine.open_positions, corr_matrix, 0.8):
                        continue

                    # --- Agent System ---
                    if agent_system:
                        order = agent_system.process(
                            symbol, direction, strat.name,
                            current_prices[symbol], adx_val, atr_ratio,
                            current_time, engine.open_positions, lots=0,
                            risk_dist=risk_dist
                        )
                        if order is None:
                            continue

                    # --- RL Agent ---
                    if rl_agent and not agent_system:
                        atr_sma_val = atr_sma_map.get(symbol, [atr_val])[min(bar_idx, len(atr_sma_map.get(symbol, [atr_val])) - 1)]
                        atr_regime_ratio = atr_val / (atr_sma_val + 1e-10)
                        tp_mult, sl_mult, rl_action_idx = rl_agent.select_action(strat.name, adx_val, atr_regime_ratio)
                        if direction == 'BUY':
                            rl_sl = current_prices[symbol] - risk_dist * sl_mult
                            rl_tp = current_prices[symbol] + risk_dist * tp_mult
                        else:
                            rl_sl = current_prices[symbol] + risk_dist * sl_mult
                            rl_tp = current_prices[symbol] - risk_dist * tp_mult

                    # --- Execute Trade ---
                    if agent_system and order:
                        lot = order.lots
                        exec_sl = order.sl
                        exec_tp = order.tp
                    elif rl_agent and not agent_system:
                        risk_pct = kelly_agent.get_risk_percent(strat.name) if kelly_agent else 0.2
                        lot = engine.calculate_lot_size(symbol, risk_pct * 100, risk_dist, engine.equity)
                        exec_sl = rl_sl
                        exec_tp = rl_tp
                    else:
                        risk_pct = kelly_agent.get_risk_percent(strat.name) if kelly_agent else 0.2
                        lot = engine.calculate_lot_size(symbol, risk_pct * 100, risk_dist, engine.equity)
                        exec_sl = row['sl']
                        exec_tp = row['tp']

                    exec_ok = engine.execute_trade(
                        symbol, strat.name, direction, lot,
                        current_prices[symbol], exec_sl, exec_tp,
                        f"{direction} Signal"
                    )
                    if exec_ok and rl_agent and not agent_system:
                        engine.open_positions[-1]['rl_action'] = (adx_val, atr_ratio, rl_action_idx)
                    if exec_ok and feat is not None:
                        engine.open_positions[-1]['meta_features'] = feat

                    # Inline feedback: process newly closed trades
                    while len(engine.closed_trades) > processed_trades:
                        t_closed = engine.closed_trades[processed_trades]
                        s_name = t_closed.get('strategy', '')
                        was_profitable = t_closed.get('profit', 0) > 0
                        if enable_meta and s_name in meta_filters:
                            mf = meta_filters[s_name]
                            mf.add_signal(t_closed.get('meta_features', {}), was_profitable)
                            if len(mf._feature_buffer) >= mf.min_samples and len(mf._feature_buffer) % 50 == 0:
                                mf.train()
                        if 'rl_action_idx' in t_closed and t_closed['rl_action_idx'] is not None:
                            rl_idx = t_closed['rl_action_idx']
                            rl_adx = t_closed.get('rl_adx', 25)
                            rl_atr = t_closed.get('rl_atr_ratio', 1.0)
                            rl_agent.update(t_closed.get('strategy', 'unknown'), rl_adx, rl_atr, rl_idx, t_closed.get('profit', 0))
                        processed_trades += 1

    engine.emergency_close_all(current_prices)

    # Drain remaining closed trades (from emergency_close_all)
    while len(engine.closed_trades) > processed_trades:
        t_closed = engine.closed_trades[processed_trades]
        s_name = t_closed.get('strategy', '')
        was_profitable = t_closed.get('profit', 0) > 0
        if enable_meta and s_name in meta_filters:
            meta_filters[s_name].add_signal(t_closed.get('meta_features', {}), was_profitable)
        if 'rl_action_idx' in t_closed and t_closed['rl_action_idx'] is not None and rl_agent:
            rl_idx = t_closed['rl_action_idx']
            rl_adx = t_closed.get('rl_adx', 25)
            rl_atr = t_closed.get('rl_atr_ratio', 1.0)
            rl_agent.update(s_name, rl_adx, rl_atr, rl_idx, t_closed.get('profit', 0))
        if kelly_agent:
            kelly_agent.update(s_name, t_closed.get('profit', 0))
        processed_trades += 1
    if enable_meta:
        for mf in meta_filters.values():
            mf.train()

    logger.info("Backtest finished. Calculating metrics...")
    port = calculate_metrics(engine.closed_trades, engine.equity_curve, engine.initial_balance)

    for point in engine.equity_curve:
        point['date'] = point['date'].strftime('%Y-%m-%d')
    for t in engine.closed_trades:
        t['entry_time'] = t['entry_time'].strftime('%Y-%m-%d %H:%M:%S')
        t['close_time'] = t['close_time'].strftime('%Y-%m-%d %H:%M:%S')

    results = {
        'mode': mode,
        'portfolio': port,
        'equity_curve': engine.equity_curve,
        'all_trades': engine.closed_trades,
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
    return port, len(engine.closed_trades), engine.equity_curve, engine.closed_trades, rl_agent, meta_filters, kelly_agent

def fmt_val(k, v):
    if k in ('net_profit', 'expectancy'):
        return f"${v:>8.2f}"
    if k in ('total_return', 'win_rate', 'max_drawdown'):
        return f"{v:>7.2f}%"
    return f"{v:>8.2f}"

def combine_results():
    """Load individual OOS splits and combine into main results.json for dashboard."""
    abs_dir = os.path.abspath(RESULTS_DIR)
    splits = {}
    for mode in ['train', 'validation', 'test']:
        with open(os.path.join(abs_dir, f'oos_{mode}.json')) as f:
            splits[mode] = json.load(f)

    # Merge equity curves chronologically
    all_equity = []
    for mode in ['train', 'validation', 'test']:
        all_equity.extend(splits[mode].get('equity_curve', []))
    # Deduplicate by date (keep first occurrence)
    seen_dates = set()
    merged_equity = []
    for pt in all_equity:
        if pt['date'] not in seen_dates:
            seen_dates.add(pt['date'])
            merged_equity.append(pt)

    # Merge all trades
    all_trades = []
    for mode in ['train', 'validation', 'test']:
        all_trades.extend(splits[mode].get('all_trades', []))

    # Calculate combined portfolio metrics
    if all_trades:
        port_metrics = calculate_metrics(all_trades, merged_equity, 100000.0)
    else:
        port_metrics = splits['train'].get('portfolio', {})

    # Strategy metrics from all trades combined
    df_trades = pd.DataFrame(all_trades)
    strat_metrics = []
    if not df_trades.empty:
        strategy_names = [
            'AVWAP_Confluence', 'ADX_TrendStrength', 'Hidden_Divergence',
            'Donchian_Breakout', 'Bollinger Mean Reversion',
            'Smart_Swing_Bias', 'PriceAction_SR',
        ]
        for sname in strategy_names:
            st = df_trades[df_trades['strategy'] == sname]
            if st.empty:
                strat_metrics.append({'name': sname, 'category': '', 'total_trades': 0, 'win_rate': 0.0, 'profit_factor': 0.0, 'net_profit': 0.0})
            else:
                wins = st[st['profit'] > 0]
                losses = st[st['profit'] <= 0]
                wr = len(wins) / len(st) * 100
                gp = wins['profit'].sum()
                gl = abs(losses['profit'].sum())
                pf = gp / gl if gl > 0 else float('inf')
                strat_metrics.append({
                    'name': sname,
                    'category': '',
                    'total_trades': len(st),
                    'win_rate': round(wr, 2),
                    'profit_factor': round(pf, 2),
                    'net_profit': round(st['profit'].sum(), 2),
                })
    # Ensure all values are JSON-safe
    for k, v in port_metrics.items():
        if hasattr(v, 'item'):
            port_metrics[k] = v.item()
    for s in strat_metrics:
        for k, v in s.items():
            if hasattr(v, 'item'):
                s[k] = v.item()

    results = {
        'portfolio': port_metrics,
        'strategies': strat_metrics,
        'equity_curve': merged_equity,
        'recent_trades': all_trades[-100:],
    }

    out_path = os.path.join(abs_dir, 'results.json')
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=4, cls=NumpyEncoder)
    print(f"\nCombined results saved to {out_path}")
    print(f"Total trades: {len(all_trades)}, Equity points: {len(merged_equity)}")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if mode == 'all':
        modes = ['train', 'validation', 'test']
        results_map = {}
        persisted_rl = None
        persisted_meta = None
        persisted_kelly = None
        
        for m in modes:
            port, trades, eq, closed, persisted_rl, persisted_meta, persisted_kelly = run_oos(m, persisted_rl, persisted_meta, persisted_kelly)
            results_map[m] = port
            
        print("\n\n========== 3-WAY SPLIT COMPARISON ==========")
        print(f"{'Metric':<20} {'TRAIN (60%)':<20} {'VAL (20%)':<20} {'TEST (20%)':<20} {'STABLE?':<10}")
        print("-" * 90)
        keys = ['total_return', 'net_profit', 'total_trades', 'win_rate', 'profit_factor', 'max_drawdown', 'sharpe_ratio', 'expectancy']
        for k in keys:
            tv = results_map['train'].get(k, 0)
            vv = results_map['validation'].get(k, 0)
            tsv = results_map['test'].get(k, 0)
            vals = [results_map[m].get(k, 0) for m in modes]
            stable = "YES" if all(v > 0 for v in vals[:2]) and abs(vals[1] - vals[2]) / max(abs(vals[2]), 0.01) < 0.5 else "CHECK"
            if k == 'max_drawdown':
                stable = "YES" if max(vals) < -3 else "CHECK"
            if k == 'profit_factor':
                stable = "YES" if all(v > 1.0 for v in vals) else "NO" if any(v < 1.0 for v in vals) else "CHECK"
            print(f"{k:<20} {fmt_val(k, tv):<20} {fmt_val(k, vv):<20} {fmt_val(k, tsv):<20} {stable:<10}")
        combine_results()
    elif mode == 'combine':
        combine_results()
    else:
        run_oos(mode)
