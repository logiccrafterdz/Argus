import os
import time
import hashlib
import inspect
import pickle
import pandas as pd
import numpy as np
import json
from engine import BacktestEngine
from json_encoder import NumpyEncoder
from indicators import MarketRegime, detect_market_context
from config import load_config, create_default_config
from log_setup import get_logger, setup_logger
from allocator import InstitutionalAllocator

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PARQUET_DIR = os.path.join(DATA_DIR, "parquet")

from strategies.avwap_confluence import AVWAPConfluence
from strategies.trend_pullback import TrendPullback
from strategies.sr_breakout_retest import SRBreakoutRetest
from strategies.bollinger_mr import BollingerMeanReversion
from strategies.orb_session import ORBSession
from strategies.orb_hybrid import ORBHybrid
from strategies.liq_sweep import LiquiditySweepFVG
from strategies.liq_sweep_breakout import LiquiditySweepBreakout
from strategies.hidden_divergence import HiddenDivergence
from strategies.ict_killzone import ICTKillzoneMacro
from strategies.vwap_multiband_regime import VWAPMultiBandRegime
from strategies.smart_swing_bias import SmartSwingBias
from strategies.price_action_sr import PriceActionSR
from strategies.volatility_squeeze import VolatilitySqueeze
from strategies.asian_range_fakeout import AsianRangeFakeout
from strategies.ny_session_reversal import NYSessionReversal
from strategies.pdh_pdl_break_reversal import PDHPDLBreakReversal as PDH_PDL_BreakReversal
from strategies.donchian_breakout import DonchianBreakout
from strategies.adx_trend_strength import ADXTrendStrength
from strategies.supertrend_ema import SuperTrendEMA


def load_data():
    symbols_data = {}
    use_parquet = os.path.isdir(PARQUET_DIR) and os.listdir(PARQUET_DIR)
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".csv"):
            continue
        parts = filename.split('.')[0].split('_')
        symbol = parts[0]
        tf = '_'.join(parts[1:])

        # Try Parquet first
        if use_parquet:
            parquet_path = os.path.join(PARQUET_DIR, filename.replace(".csv", ".parquet"))
            if os.path.exists(parquet_path):
                df = pd.read_parquet(parquet_path)
            else:
                df = pd.read_csv(os.path.join(DATA_DIR, filename), parse_dates=['time'])
        else:
            df = pd.read_csv(os.path.join(DATA_DIR, filename), parse_dates=['time'])

        df = df[(df['time'] >= '2024-01-01') & (df['time'] <= '2025-06-01')]
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
    """
    Compute signals for one strategy across all symbols.
    Runs in a thread — each thread owns its own strategy instance, no shared state.
    """
    strat, data_items, regimes_dict, cache_file = args

    # --- Cache check: load if exists ---
    if cache_file and os.path.exists(cache_file):
        with open(cache_file, 'rb') as _f:
            return pickle.load(_f)

    # Determine timeframe for this strategy
    M15_STRATS = {'ICT_Killzone_Macro', 'ORB_Session', 'ORB_Hybrid',
                  'Asian_Range_Fakeout', 'NY_Session_Reversal', 'PDH_PDL_BreakReversal'}
    H4_STRATS  = {'PriceAction_SR', 'Donchian_Breakout', 'Smart_Swing_Bias'}
    if strat.name in M15_STRATS:
        tf = 'M15'
    elif strat.name in H4_STRATS:
        tf = 'H4'
    else:
        tf = 'H1'

    local_results = []

    for symbol, tfs in data_items:
        if tf not in tfs:
            continue
        df = tfs[tf].copy()
        df.reset_index(inplace=True)
        df = strat.prepare_data(df)

        sig_col = df['signal'].values
        sig_idx = np.where(sig_col != 0)[0]
        if len(sig_idx) == 0:
            continue

        regimes_sym = regimes_dict.get(symbol, {})
        records     = df.to_dict('records')

        for i in sig_idx:
            r  = records[int(i)]
            ts = r['time']

            d_regime = regimes_sym.get(ts.normalize(), 1)
            if not strat.check_regime(d_regime):
                continue

            h = ts.hour
            if   0 <= h <  8: cs = 1
            elif 8 <= h < 16: cs = 2
            elif 13 <= h < 22: cs = 4
            else:              cs = 0
            if not strat.check_session(cs):
                continue

            sl_price = r.get('sl', None)
            if sl_price is None or sl_price == 0:
                continue
            if abs(r['close'] - sl_price) <= 0:
                continue

            local_results.append((ts, {
                'symbol':        symbol,
                'strategy':      strat.name,
                'strategy_type': strat.strategy_type,
                'order_type':    'BUY' if r['signal'] == 1 else 'SELL',
                'entry_price':   r['close'],
                'atr_value':     r.get('atr', 0),
                'conviction':    r.get('conviction', 0.5),
                'sl_price':      sl_price,
                'tp_price':      r.get('tp', None),
            }))

    # --- Cache save ---
    if cache_file:
        try:
            with open(cache_file, 'wb') as _f:
                pickle.dump(local_results, _f, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            pass

    return local_results


def _compute_strategy_cache_key(strat, data):
    """
    Unique hash of strategy source code + data fingerprint.
    Triggers automatic cache invalidation when code or data changes.
    """
    h = hashlib.md5()
    try:
        src = inspect.getsource(type(strat))
        h.update(src.encode('utf-8', errors='ignore'))
    except Exception:
        h.update(strat.name.encode())
    for sym in sorted(data.keys()):
        h.update(sym.encode())
        for tf in sorted(data[sym].keys()):
            df = data[sym][tf]
            if not df.empty:
                h.update(f"{tf}:{len(df)}:{df.index[0]}:{df.index[-1]}".encode())
    return h.hexdigest()[:12]


def run_backtest():
    np.random.seed(42)
    setup_logger('backtest')
    logger = get_logger('backtest')
    config = load_config()
    if config is None:
        config = create_default_config()

    logger.info("Loading historical data...")
    t0 = time.perf_counter()
    data = load_data()
    logger.info(f"Data loaded: {len(data)} symbols in {time.perf_counter()-t0:.2f}s")

    engine = BacktestEngine(
        initial_balance=config.get('backtest', {}).get('initial_balance', 100000.0),
        config=config
    )

    strategies = [
        AVWAPConfluence(),
        TrendPullback(),
        BollingerMeanReversion(),
        HiddenDivergence(),
        SmartSwingBias(),
        PriceActionSR(),
        VolatilitySqueeze(),
        AsianRangeFakeout(),
        NYSessionReversal(),
        LiquiditySweepBreakout(),
        SuperTrendEMA(),
    ]

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

    # Build regime dict EARLY (needed for signal schedule)
    logger.info("Building regime dict per symbol...")
    regimes_dict = {}
    for sym in data.keys():
        if 'H4' in data[sym]:
            h4_df = data[sym]['H4']
            d1_df = h4_df.resample('D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
            m_regime = MarketRegime(d1_df)
            regimes_dict[sym] = m_regime.to_dict()
        elif 'H1' in data[sym]:
            h1_df = data[sym]['H1']
            d1_df = h1_df.resample('D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
            m_regime = MarketRegime(d1_df)
            regimes_dict[sym] = m_regime.to_dict()
        else:
            regimes_dict[sym] = {}

    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Signal cache: one .pkl file per strategy, keyed by code+data hash
    CACHE_DIR = os.path.join(os.path.dirname(__file__), '.signal_cache')
    os.makedirs(CACHE_DIR, exist_ok=True)

    n_workers  = min(len(strategies), 8)
    data_items = list(data.items())

    # Build work args: one entry per strategy with its cache file path
    work_args = []
    for strat in strategies:
        key        = _compute_strategy_cache_key(strat, data)
        cache_file = os.path.join(CACHE_DIR, f'{strat.name}_{key}.pkl')
        work_args.append((strat, data_items, regimes_dict, cache_file))

    cached_count  = sum(1 for a in work_args if os.path.exists(a[3]))
    compute_count = len(work_args) - cached_count

    logger.info(f"Pre-calculating signals — {len(strategies)} strats x {len(data)} symbols "
                f"| cache hits: {cached_count}/{len(strategies)}, to compute: {compute_count}")
    t_precalc_start = time.perf_counter()
    signal_schedule = {}

    with ThreadPoolExecutor(max_workers=max(1, min(n_workers, len(work_args)))) as executor:
        futures = {executor.submit(_compute_strategy_signals, a): a[0].name for a in work_args}
        for future in as_completed(futures):
            strat_name = futures[future]
            try:
                for ts, sig in future.result():
                    if ts not in signal_schedule:
                        signal_schedule[ts] = []
                    signal_schedule[ts].append(sig)
            except Exception as exc:
                logger.error(f"Strategy {strat_name} failed in pre-calc: {exc}")

    t_precalc_dur = time.perf_counter() - t_precalc_start
    all_sigs = sum(len(v) for v in signal_schedule.values())
    logger.info(f"Signal schedule built: {len(signal_schedule)} bars with signals, "
                f"total: {all_sigs} [{t_precalc_dur:.2f}s]")

    # Debug: check timestamp match
    sample_ts = next(iter(signal_schedule.keys()))
    logger.info(f"  Sample sig ts: {sample_ts} type={type(sample_ts).__name__}")
    logger.info(f"  Timeline range: {master_timeline.index[0]} to {master_timeline.index[-1]}")
    timeline_set = set(master_timeline.index)
    match_total = sum(1 for ts in signal_schedule if ts in timeline_set)
    logger.info(f"  All signal ts in master_timeline: {match_total}/{len(signal_schedule)}")

    # [REMOVED] regimes_dict duplicate build

    # Build timeline_prices: { timestamp -> { symbol -> (close, high, low) } }
    # Pre-built once before the main loop for O(1) per-bar price lookup
    logger.info("Building timeline_prices lookup...")
    t_tp = time.perf_counter()
    timeline_prices = {}
    for symbol, tfs in data.items():
        tf_name = 'M15' if 'M15' in tfs else ('H1' if 'H1' in tfs else None)
        if tf_name is None:
            continue
        df_tf = tfs[tf_name]
        arr_close = df_tf['close'].values
        arr_high  = df_tf['high'].values
        arr_low   = df_tf['low'].values
        for idx_i, ts in enumerate(df_tf.index):
            if ts not in timeline_prices:
                timeline_prices[ts] = {}
            timeline_prices[ts][symbol] = (arr_close[idx_i], arr_high[idx_i], arr_low[idx_i])
    logger.info(f"Timeline prices built: {len(timeline_prices)} unique timestamps [{time.perf_counter()-t_tp:.2f}s]")

    logger.info("Building correlation matrix...")
    h1_closes = {}
    for sym in data.keys():
        if 'H1' in data[sym]:
            h1_closes[sym] = data[sym]['H1']['close']
    corr_df = pd.DataFrame(h1_closes)
    corr_matrix = corr_df.corr()

    allocator = InstitutionalAllocator(config)
    allocator.set_corr_matrix(corr_matrix)

    # Pre-cache daily context for speed
    daily_context_cache = {}
    for date_key in sorted(set(ts.normalize() for ts in master_timeline.index)):
        eur_regime = regimes_dict.get('EURUSD', {}).get(date_key, 1)
        daily_context_cache[date_key] = eur_regime

    t_loop = time.perf_counter()
    logger.info(f"Executing backtest with {len(strategies)} strategies, DCA allocator...")
    count = 0
    total = len(master_timeline)
    total_raw = 0
    total_approved = 0
    raw_by_strat = {}
    bars_with_signals = 0
    bars_total = 0
    for current_time in master_timeline.index:
        count += 1
        if count % 10000 == 0:
            logger.info(f"Progress: {count}/{total}")

        # Phase 0: Get current prices — O(1) dict lookup, pre-built before loop
        prices_row = timeline_prices.get(current_time, {})
        current_prices = {}
        current_highs  = {}
        current_lows   = {}
        for sym, (c, h, l) in prices_row.items():
            current_prices[sym] = c
            current_highs[sym]  = h
            current_lows[sym]   = l

        current_date = current_time.normalize()
        engine.update(current_time, current_prices, current_highs, current_lows)
        allocator.reset_daily(current_date, engine.balance, engine.peak_balance)

        if engine.risk_manager.is_halted:
            continue

        # Phase 1: O(1) signal lookup
        raw_signals = signal_schedule.get(current_time, [])
        bars_total += 1
        if raw_signals:
            bars_with_signals += 1

        # Phase 2: InstitutionalAllocator filter
        try:
            throttle = allocator.throttle_multiplier()
            if throttle <= 0 or not raw_signals:
                approved_signals = []
            else:
                c_regime = daily_context_cache.get(current_date, 1)
                approved_signals = allocator.filter(raw_signals, open_positions=engine.open_positions, current_regime=c_regime)
        except Exception as e:
            logger.error(f"Allocator error at {current_time}: {e}")
            approved_signals = []

        total_raw += len(raw_signals)
        total_approved += len(approved_signals)

        # Phase 3: Execute with dynamic risk allocation
        for sig in approved_signals:
            allocation_pct = sig.get('allocated_risk_pct', 0.02) * throttle
            risk_percent = allocation_pct * 100.0

            risk_distance = abs(current_prices[sig['symbol']] - sig['sl_price']) if sig.get('sl_price') else 0
            if risk_distance <= 0:
                continue

            lot_size = engine.calculate_lot_size(
                sig['symbol'],
                risk_percent,
                risk_distance,
                engine.equity
            )
            if lot_size <= 0:
                continue

            engine.execute_trade(
                symbol=sig['symbol'],
                strategy_name=sig['strategy'],
                strategy_type=sig['strategy_type'],
                order_type=sig['order_type'],
                lot_size=lot_size,
                entry_price=sig['entry_price'],
                atr_value=sig['atr_value'],
                comment=f"{sig['strategy']}_{sig['symbol']}_{current_time.date()}",
                strategy_tp=sig['tp_price'],
                override_sl=sig['sl_price'],
                override_tp=sig['tp_price'],
            )

        if engine.is_bankrupt:
            logger.warning(f"Bankrupt at {current_time}")
            break

    engine.emergency_close_all(current_prices)
    t_loop_end = time.perf_counter()

    # Build raw_by_strat from signal_schedule
    raw_by_strat = {}
    for sigs in signal_schedule.values():
        for sig in sigs:
            raw_by_strat[sig['strategy']] = raw_by_strat.get(sig['strategy'], 0) + 1
    logger.info(f"Backtest finished. Raw signals: {total_raw}, Approved: {total_approved}, Ratio: {total_approved/max(total_raw,1):.2%}")
    logger.info(f"  Allocator skips: no_weights={allocator.skip_no_weights}, budget_full={allocator.skip_budget_full}, no_strategy={allocator.skip_no_strategy}")
    logger.info(f"  Allocator calls={allocator.allocate_calls}, signals_in={allocator.total_signals_in}, approved={allocator.total_approved}")
    logger.info(f"  Signal schedule bars={len(signal_schedule)}, avg_signals_per_bar={all_sigs/max(len(signal_schedule),1):.1f}")
    logger.info(f"  Main loop: {bars_with_signals}/{bars_total} bars had signals")
    for s, n in sorted(raw_by_strat.items(), key=lambda x: -x[1]):
        logger.info(f"  {s:30s}: {n:5d} raw signals")
    logger.info(f"  [TIME] Main loop  : {t_loop_end - t_loop:.2f}s")
    logger.info(f"  [TIME] Pre-calc   : {t_precalc_dur:.2f}s ({n_workers} threads)")
    logger.info(f"  [TIME] Total      : {t_loop_end - t0:.2f}s")
    logger.info("Calculating metrics...")

    from analytics import calculate_metrics
    port_metrics = calculate_metrics(engine.closed_trades, engine.equity_curve, 100000.0)

    df_trades = pd.DataFrame(engine.closed_trades)
    strat_metrics = []
    if not df_trades.empty:
        for strat in strategies:
            strat_trades = df_trades[df_trades['strategy'] == strat.name]
            if not strat_trades.empty:
                wins = strat_trades[strat_trades['profit'] > 0]
                losses = strat_trades[strat_trades['profit'] <= 0]
                win_rate = len(wins) / len(strat_trades) * 100
                gross_profit = wins['profit'].sum()
                gross_loss = abs(losses['profit'].sum())
                pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                strat_metrics.append({
                    'name': strat.name,
                    'category': strat.category,
                    'total_trades': len(strat_trades),
                    'win_rate': round(win_rate, 2),
                    'profit_factor': round(pf, 2),
                    'net_profit': round(strat_trades['profit'].sum(), 2)
                })
            else:
                strat_metrics.append({
                    'name': strat.name, 'category': strat.category,
                    'total_trades': 0, 'win_rate': 0.0,
                    'profit_factor': 0.0, 'net_profit': 0.0
                })

    try:
        # بناء equity_curve مرة واحدة فقط (property → لا نستدعيه 3 مرات)
        eq_curve = engine.equity_curve
        for point in eq_curve:
            if hasattr(point['date'], 'strftime'):
                point['date'] = point['date'].strftime('%Y-%m-%d %H:%M:%S')
        for t in engine.closed_trades:
            t['entry_time'] = t['entry_time'].strftime('%Y-%m-%d %H:%M:%S')
            t['close_time'] = t['close_time'].strftime('%Y-%m-%d %H:%M:%S')

        for s in strat_metrics:
            for k, v in s.items():
                if hasattr(v, 'item'):
                    s[k] = v.item()
        for k, v in port_metrics.items():
            if hasattr(v, 'item'):
                port_metrics[k] = v.item()

        results = {
            'portfolio': port_metrics,
            'strategies': strat_metrics,
            'equity_curve': eq_curve,
            'recent_trades': engine.closed_trades[-100:]
        }

        RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "data")
        os.makedirs(RESULTS_DIR, exist_ok=True)
        with open(os.path.join(RESULTS_DIR, 'results.json'), 'w') as f:
            json.dump(results, f, indent=4, cls=NumpyEncoder)

        logger.info(f"Results saved to {os.path.join(RESULTS_DIR, 'results.json')}")
    except Exception as e:
        logger.error(f"FAILED TO SAVE JSON: {e}")

    logger.info(f"Portfolio metrics: PF={port_metrics.get('profit_factor', 0):.2f}, "
                f"Trades={port_metrics.get('total_trades', 0)}, "
                f"Net=${port_metrics.get('net_profit', 0):,.2f}, "
                f"DD={port_metrics.get('max_drawdown', 0):.2f}%")

    return results


if __name__ == "__main__":
    run_backtest()
