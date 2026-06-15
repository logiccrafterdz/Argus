import os
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
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".csv"):
            parts = filename.split('.')[0].split('_')
            symbol = parts[0]
            tf = '_'.join(parts[1:])
            filepath = os.path.join(DATA_DIR, filename)
            df = pd.read_csv(filepath, parse_dates=['time'])
            df = df[(df['time'] >= '2024-01-01') & (df['time'] <= '2025-06-01')]
            if len(df) < 500:
                continue
            df.set_index('time', inplace=True)
            if symbol not in symbols_data:
                symbols_data[symbol] = {}
            symbols_data[symbol][tf] = df
    return symbols_data


def run_backtest():
    np.random.seed(42)
    setup_logger('backtest')
    logger = get_logger('backtest')
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

    logger.info("Pre-calculating strategy signals...")
    precalc_data = {}
    for symbol, tfs in data.items():
        precalc_data[symbol] = {}
        for strat in strategies:
            tf = 'H1'
            if strat.name in ['ICT_Killzone_Macro', 'ORB_Session', 'ORB_Hybrid',
                              'Asian_Range_Fakeout', 'NY_Session_Reversal', 'PDH_PDL_BreakReversal']:
                tf = 'M15'
            elif strat.name in ['PriceAction_SR', 'Donchian_Breakout', 'Smart_Swing_Bias']:
                tf = 'H4'

            if tf not in tfs:
                continue
            df = tfs[tf].copy()
            df.reset_index(inplace=True)
            df = strat.prepare_data(df)
            df.set_index('time', inplace=True)
            if tf not in precalc_data[symbol]:
                precalc_data[symbol][tf] = {}
            precalc_data[symbol][tf][strat.name] = df

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

    logger.info("Building correlation matrix...")
    h1_closes = {}
    for sym in data.keys():
        if 'H1' in data[sym]:
            h1_closes[sym] = data[sym]['H1']['close']
    corr_df = pd.DataFrame(h1_closes)
    corr_matrix = corr_df.corr()

    logger.info("Converting to fast dict lookups...")
    dict_data = {}
    for symbol, tfs in data.items():
        dict_data[symbol] = {}
        for tf_name, df in tfs.items():
            dict_data[symbol][tf_name] = df.to_dict('index')

    dict_precalc = {}
    for symbol, tfs in precalc_data.items():
        dict_precalc[symbol] = {}
        for tf, strat_data in tfs.items():
            dict_precalc[symbol][tf] = {}
            for strat_name, df in strat_data.items():
                dict_precalc[symbol][tf][strat_name] = df.to_dict('index')

    allocator = InstitutionalAllocator(config)
    allocator.set_corr_matrix(corr_matrix)

    logger.info(f"Executing backtest with {len(strategies)} strategies, DCA allocator...")
    count = 0
    total = len(master_timeline)
    for current_time in master_timeline.index:
        count += 1
        if count % 10000 == 0:
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

        # Phase 1: Collect raw signals from all strategies
        raw_signals = []
        c_regime = 1
        for symbol, tfs in dict_precalc.items():
            if symbol not in current_prices:
                continue

            sym_regime_dict = regimes_dict.get(symbol, {})
            c_regime = sym_regime_dict.get(current_date, 1)

            for tf, strat_data in tfs.items():
                if tf == 'M15':
                    if 'M15' not in dict_data[symbol] or current_time not in dict_data[symbol]['M15']:
                        continue
                elif tf == 'H1':
                    if current_time.minute != 0:
                        continue
                    if 'H1' not in dict_data[symbol] or current_time not in dict_data[symbol]['H1']:
                        continue
                elif tf == 'H4':
                    if current_time.minute != 0 or current_time.hour % 4 != 0:
                        continue
                    if 'H4' not in dict_data[symbol] or current_time not in dict_data[symbol]['H4']:
                        continue

                for strat in strategies:
                    if strat.name not in strat_data:
                        continue
                    if not strat.check_regime(c_regime) or not strat.check_session(c_session):
                        continue
                    if current_time not in strat_data[strat.name]:
                        continue

                    row = strat_data[strat.name][current_time]
                    entry_signal = row.get('signal', 0)
                    if entry_signal == 0:
                        continue

                    atr_value = row.get('atr', 0)
                    conviction = row.get('conviction', 0.5)
                    sl_price = row.get('sl', None)
                    tp_price = row.get('tp', None)

                    risk_distance = abs(current_prices[symbol] - sl_price) if sl_price else 0
                    if risk_distance <= 0:
                        continue

                    raw_signals.append({
                        'symbol': symbol,
                        'strategy': strat.name,
                        'strategy_type': strat.strategy_type,
                        'order_type': 'BUY' if entry_signal == 1 else 'SELL',
                        'entry_price': current_prices[symbol],
                        'atr_value': atr_value,
                        'conviction': conviction,
                        'sl_price': sl_price,
                        'tp_price': tp_price,
                    })

        # Phase 2: InstitutionalAllocator filter (regime-aware DCA)
        try:
            approved_signals = allocator.filter(raw_signals, open_positions=engine.open_positions, current_regime=c_regime)
        except Exception as e:
            logger.error(f"Allocator error at {current_time}: {e}")
            approved_signals = []

        # Phase 3: Execute with dynamic risk allocation
        for sig in approved_signals:
            allocation_pct = sig.get('allocated_risk_pct', 0.02)
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

    logger.info("Backtest finished. Calculating metrics...")

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
        for point in engine.equity_curve:
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
            'equity_curve': engine.equity_curve,
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
                f"DD={port_metrics.get('max_drawdown_pct', 0):.2f}%")

    return results


if __name__ == "__main__":
    run_backtest()
