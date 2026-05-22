import os
import pandas as pd
import json
from engine import BacktestEngine
from analytics import calculate_metrics
import numpy as np
from json_encoder import NumpyEncoder
from strategies.trend_pullback import TrendPullback
from strategies.ict_killzone import ICTKillzoneMacro
from strategies.bollinger_mr import BollingerMeanReversion
from strategies.liq_sweep import LiquiditySweepFVG
from strategies.sr_breakout_retest import SRBreakoutRetest
from strategies.orb_session import ORBSession
from strategies.orb_hybrid import ORBHybrid
from strategies.price_action_sr import PriceActionSR
from strategies.liq_sweep_breakout import LiquiditySweepBreakout
from strategies.vwap_multiband_regime import VWAPMultiBandRegime
from strategies.avwap_confluence import AVWAPConfluence
from strategies.asian_range_fakeout import AsianRangeFakeout
from strategies.ny_session_reversal import NYSessionReversal
from strategies.volatility_squeeze import VolatilitySqueeze
from strategies.smart_swing_bias import SmartSwingBias
from strategies.supertrend_ema import SuperTrendEMA
from strategies.hidden_divergence import HiddenDivergence
from strategies.adx_trend_strength import ADXTrendStrength
from strategies.donchian_breakout import DonchianBreakout
from strategies.pdh_pdl_break_reversal import PDHPDLBreakReversal
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

def run_backtest():
    logger = setup_logger('backtest', log_file='backtest.log')
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
        TrendPullback(),
        ICTKillzoneMacro(),
        BollingerMeanReversion(),
        LiquiditySweepFVG(),
        SRBreakoutRetest(),
        ORBSession(),
        ORBHybrid(),
        PriceActionSR(),
        LiquiditySweepBreakout(),
        VWAPMultiBandRegime(),
        AVWAPConfluence(),
        AsianRangeFakeout(),
        NYSessionReversal(),
        VolatilitySqueeze(),
        SmartSwingBias(),
        SuperTrendEMA(),
        HiddenDivergence(),
        ADXTrendStrength(),
        DonchianBreakout(),
        PDHPDLBreakReversal()
    ]
    
    # Build master timeline from all available M15 data, plus H1 for symbols without M15
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
        for strat_idx, strat in enumerate(strategies):
            # Select appropriate TF
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
                if tf not in precalc_data[symbol]:
                    precalc_data[symbol][tf] = {}
                precalc_data[symbol][tf][strat.name] = df

    # Prepare daily regime for filtering
    # Use EURUSD D1 or resample H4 to D1 for regime
    eurusd_h4 = data['EURUSD']['H4']
    eurusd_d1 = eurusd_h4.resample('D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    global_regime = MarketRegime(eurusd_d1)
    
    # Build correlation matrix from H1 close prices for all symbols
    logger.info("Building correlation matrix...")
    all_symbols = list(data.keys())
    h1_closes = {}
    for sym in all_symbols:
        if 'H1' in data[sym]:
            h1_closes[sym] = data[sym]['H1']['close']
    
    corr_df = pd.DataFrame(h1_closes)
    corr_matrix = corr_df.corr()
    logger.info(f"Correlation matrix built for {len(corr_matrix.columns)} symbols.")
    
    logger.info("Converting historical data to fast dict lookups...")
    dict_data = {}
    for symbol, tfs in data.items():
        dict_data[symbol] = {}
        for tf_name, df in tfs.items():
            dict_data[symbol][tf_name] = df.to_dict('index')
            
    logger.info("Converting strategy precalculated data to fast dict lookups...")
    dict_precalc = {}
    for symbol, tfs in precalc_data.items():
        dict_precalc[symbol] = {}
        for tf, strat_data in tfs.items():
            dict_precalc[symbol][tf] = {}
            for strat_name, df in strat_data.items():
                dict_precalc[symbol][tf][strat_name] = df.to_dict('index')
                
    global_regime_dict = global_regime.to_dict()

    logger.info("Executing backtest over timeline...")
    count = 0
    total = len(master_timeline)
    for current_time in master_timeline.index:
        count += 1
        if count % 10000 == 0:
            logger.info(f"Progress: {count}/{total}")
            
        current_prices = {}
        current_highs = {}
        current_lows = {}
        
        # Get current state — prefer M15, fallback to H1
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
                
        # Current Regime (Daily)
        current_date = current_time.normalize()
        c_regime = global_regime_dict.get(current_date, 1) # fallback Trend
            
        c_session = 0
        h = current_time.hour
        if 0 <= h < 8: c_session |= 1 # Asian
        if 8 <= h < 16: c_session |= 2 # London
        if 13 <= h < 22: c_session |= 4 # NY

        engine.update(current_time, current_prices, current_highs, current_lows)
        
        if engine.risk_manager.is_halted:
            continue
            
        # Strategy Signals
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
                    if not strat.check_regime(c_regime) or not strat.check_session(c_session): continue
                    
                    if current_time in strat_data[strat.name]:
                        row = strat_data[strat.name][current_time]
                    else:
                        continue
                    
                    if row['signal'] == 1:
                        risk_dist = current_prices[symbol] - row['sl']
                        if risk_dist <= 0 or pd.isna(risk_dist): continue
                        if not engine.risk_manager.check_correlation(symbol, 'BUY', engine.open_positions, corr_matrix, 0.8): continue
                        lot = engine.calculate_lot_size(symbol, 1.0, risk_dist, engine.equity)
                        engine.execute_trade(symbol, strat.name, 'BUY', lot, current_prices[symbol], row['sl'], row['tp'], "Buy Signal")
                    elif row['signal'] == -1:
                        risk_dist = row['sl'] - current_prices[symbol]
                        if risk_dist <= 0 or pd.isna(risk_dist): continue
                        if not engine.risk_manager.check_correlation(symbol, 'SELL', engine.open_positions, corr_matrix, 0.8): continue
                        lot = engine.calculate_lot_size(symbol, 1.0, risk_dist, engine.equity)
                        engine.execute_trade(symbol, strat.name, 'SELL', lot, current_prices[symbol], row['sl'], row['tp'], "Sell Signal")
                        
    # End of backtest, close all
    engine.emergency_close_all(current_prices)
    
    logger.info("Backtest finished. Calculating metrics...")
    
    # Portfolio Metrics
    port_metrics = calculate_metrics(engine.closed_trades, engine.equity_curve, 100000.0)
    
    # Strategy Metrics
    df_trades = pd.DataFrame(engine.closed_trades)
    strat_metrics = []
    if not df_trades.empty:
        for strat in strategies:
            strat_trades = df_trades[df_trades['strategy'] == strat.name]
            if not strat_trades.empty:
                # We do not have individual equity curves, but we can compute basic metrics
                total_trades = len(strat_trades)
                wins = strat_trades[strat_trades['profit'] > 0]
                losses = strat_trades[strat_trades['profit'] <= 0]
                win_rate = len(wins) / total_trades * 100
                gross_profit = wins['profit'].sum()
                gross_loss = abs(losses['profit'].sum())
                pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                
                strat_metrics.append({
                    'name': strat.name,
                    'category': strat.category,
                    'total_trades': total_trades,
                    'win_rate': round(win_rate, 2),
                    'profit_factor': round(pf, 2),
                    'net_profit': round(strat_trades['profit'].sum(), 2)
                })
            else:
                strat_metrics.append({
                    'name': strat.name,
                    'category': strat.category,
                    'total_trades': 0,
                    'win_rate': 0.0,
                    'profit_factor': 0.0,
                    'net_profit': 0.0
                })

    try:
        # Prepare JSON output
        # Format dates for JSON
        for point in engine.equity_curve:
            point['date'] = point['date'].strftime('%Y-%m-%d')
            
        for t in engine.closed_trades:
            t['entry_time'] = t['entry_time'].strftime('%Y-%m-%d %H:%M:%S')
            t['close_time'] = t['close_time'].strftime('%Y-%m-%d %H:%M:%S')
            
        # Convert any Series or un-serializable objects inside strat_metrics
        for s in strat_metrics:
            for k, v in s.items():
                if hasattr(v, 'item'):
                    s[k] = v.item()
                    
        # Make sure portfolio metrics values are floats/ints
        for k, v in port_metrics.items():
            if hasattr(v, 'item'):
                port_metrics[k] = v.item()
                
        results = {
            'portfolio': port_metrics,
            'strategies': strat_metrics,
            'equity_curve': engine.equity_curve,
            'recent_trades': engine.closed_trades[-100:] # Last 100
        }
        
        abs_results_dir = os.path.abspath(RESULTS_DIR)
        if not os.path.exists(abs_results_dir):
            os.makedirs(abs_results_dir)
            
        with open(os.path.join(abs_results_dir, 'results.json'), 'w') as f:
            json.dump(results, f, indent=4, cls=NumpyEncoder)
            
        logger.info(f"Results saved to {os.path.join(abs_results_dir, 'results.json')}")
    except Exception as e:
        logger.error(f"FAILED TO SAVE JSON: {e}")
        
    logger.info(f"Portfolio metrics: {port_metrics}")

if __name__ == "__main__":
    run_backtest()
