import os
import pandas as pd
import json
from engine import BacktestEngine
from analytics import calculate_metrics
from strategies.trend_pullback import TrendPullback
from strategies.ict_killzone import ICTKillzoneMacro
from strategies.bollinger_mr import BollingerMeanReversion
from strategies.liq_sweep import LiquiditySweepFVG
from indicators import MarketRegime

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
    print("Loading historical data...")
    data = load_data()
    print("Data loaded.")
    
    engine = BacktestEngine(initial_balance=100000.0)
    
    strategies = [
        TrendPullback(),
        ICTKillzoneMacro(),
        BollingerMeanReversion(),
        LiquiditySweepFVG()
    ]
    
    # For simplicity, we resample everything to a unified timeline (e.g. H1)
    # In a real tick-by-tick or bar-by-bar engine we'd step through time.
    # Here we'll create a master timeline from M15 and step through it.
    
    master_timeline = None
    for symbol, tfs in data.items():
        if 'M15' in tfs:
            if master_timeline is None:
                master_timeline = pd.Series(index=tfs['M15'].index, dtype=float)
            else:
                master_timeline = master_timeline.combine_first(pd.Series(index=tfs['M15'].index, dtype=float))
                
    master_timeline = master_timeline.sort_index()
    
    print("Pre-calculating strategy signals...")
    precalc_data = {}
    for symbol, tfs in data.items():
        precalc_data[symbol] = {}
        for strat_idx, strat in enumerate(strategies):
            # Select appropriate TF
            tf = 'H1'
            if strat.name == 'ICT Killzone Macro': tf = 'M15'
            elif strat.name == 'TrendPullback': tf = 'H1'
            elif strat.name == 'Bollinger Mean Reversion': tf = 'H1'
            elif strat.name == 'Liquidity Sweep FVG': tf = 'H1'
            
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
    
    print("Executing backtest over timeline...")
    count = 0
    total = len(master_timeline)
    for current_time in master_timeline.index:
        count += 1
        if count % 10000 == 0:
            print(f"Progress: {count}/{total}")
            
        current_prices = {}
        current_highs = {}
        current_lows = {}
        
        # Get current state
        for symbol, tfs in data.items():
            if 'M15' in tfs and current_time in tfs['M15'].index:
                row = tfs['M15'].loc[current_time]
                current_prices[symbol] = row['close']
                current_highs[symbol] = row['high']
                current_lows[symbol] = row['low']
                
        # Current Regime (Daily)
        current_date = current_time.normalize()
        if current_date in global_regime.index:
            c_regime = global_regime.loc[current_date]
        else:
            c_regime = 1 # fallback Trend
            
        c_session = 0
        h = current_time.hour
        if 0 <= h < 8: c_session |= 1 # Asian
        if 8 <= h < 16: c_session |= 2 # London
        if 13 <= h < 22: c_session |= 4 # NY

        engine.update(current_time, current_prices, current_highs, current_lows)
        
        if engine.risk_manager.is_halted:
            continue
            
        # Strategy Signals
        for symbol, tfs in precalc_data.items():
            for tf, strat_data in tfs.items():
                if tf == 'M15':
                    if current_time not in data[symbol]['M15'].index: continue
                elif tf == 'H1':
                    # Only execute on hour boundary
                    if current_time.minute != 0: continue
                    if current_time not in data[symbol]['H1'].index: continue
                
                for strat in strategies:
                    if strat.name not in strat_data: continue
                    if not strat.check_regime(c_regime) or not strat.check_session(c_session): continue
                    
                    row = strat_data[strat.name].loc[current_time]
                    if row['signal'] == 1:
                        risk_dist = current_prices[symbol] - row['sl']
                        # Approx 1 pip = 0.0001
                        lot = engine.risk_manager.calculate_lot_size(symbol, 1.0, risk_dist / 0.00001, engine.equity)
                        engine.execute_trade(symbol, strat.name, 'BUY', lot, current_prices[symbol], row['sl'], row['tp'], "Buy Signal")
                    elif row['signal'] == -1:
                        risk_dist = row['sl'] - current_prices[symbol]
                        lot = engine.risk_manager.calculate_lot_size(symbol, 1.0, risk_dist / 0.00001, engine.equity)
                        engine.execute_trade(symbol, strat.name, 'SELL', lot, current_prices[symbol], row['sl'], row['tp'], "Sell Signal")
                        
    # End of backtest, close all
    engine.emergency_close_all(current_prices)
    
    print("Backtest finished. Calculating metrics...")
    
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

    # Prepare JSON output
    # Format dates for JSON
    for point in engine.equity_curve:
        point['date'] = point['date'].strftime('%Y-%m-%d')
        
    for t in engine.closed_trades:
        t['entry_time'] = t['entry_time'].strftime('%Y-%m-%d %H:%M:%S')
        t['close_time'] = t['close_time'].strftime('%Y-%m-%d %H:%M:%S')
        
    results = {
        'portfolio': port_metrics,
        'strategies': strat_metrics,
        'equity_curve': engine.equity_curve,
        'recent_trades': engine.closed_trades[-100:] # Last 100
    }
    
    if not os.path.exists(RESULTS_DIR):
        os.makedirs(RESULTS_DIR)
        
    with open(os.path.join(RESULTS_DIR, 'results.json'), 'w') as f:
        json.dump(results, f, indent=4)
        
    print(f"Results saved to {os.path.join(RESULTS_DIR, 'results.json')}")
    print(port_metrics)

if __name__ == "__main__":
    run_backtest()
