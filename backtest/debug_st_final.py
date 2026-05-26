"""Check if SuperTrend_EMA trades with relaxed DD limits (5%/12%/20%)"""
import sys; sys.path.insert(0,'.')
import numpy as np
import pandas as pd
from risk_manager import RiskManager
from strategies.supertrend_ema import SuperTrendEMA

# Load data for Jan 3-15, 2022
symbol = 'XAUUSD'
h1 = pd.read_csv(f'data/{symbol}_H1.csv', parse_dates=['time'])
m15 = pd.read_csv(f'data/{symbol}_M15.csv', parse_dates=['time'])

# Filter to Jan 3-15
mask_m15 = (m15['time'] >= '2022-01-03') & (m15['time'] < '2022-01-15')
mask_h1 = (h1['time'] >= '2022-01-03') & (h1['time'] < '2022-01-15')

h1_subset = h1[mask_h1].copy()
m15_subset = m15[mask_m15].copy()

# Build precalc with SuperTrend
s = SuperTrendEMA()
df = h1_subset.copy()
df.reset_index(inplace=True)
df = s.prepare_data(df)
df.set_index('time', inplace=True)
precalc = df.to_dict('index')

# Check signals
signal_times = [(t, r['signal']) for t, r in precalc.items() if r['signal'] != 0]
print(f"SuperTrend signals in Jan 3-15: {len(signal_times)}")
for t, sig in signal_times:
    print(f"  {t}: signal={sig}")

# Build dict_data
h1_subset_idx = h1_subset.set_index('time')
m15_subset_idx = m15_subset.set_index('time')
dict_data = {symbol: {
    'M15': m15_subset_idx.to_dict('index'),
    'H1': h1_subset_idx.to_dict('index')
}}

dict_precalc = {symbol: {'H1': {s.name: precalc}}}

# Simulate execution
rm = RiskManager(100000.0)
equity = 100000.0
peak = 100000.0

master_timeline = pd.Series(index=m15_subset_idx.index, dtype=float).sort_index()

for current_time in master_timeline.index:
    # Get price
    row = dict_data[symbol]['M15'].get(current_time)
    if not row:
        continue
    price = row['close']
    current_prices = {symbol: price}
    
    # Risk manager update
    rm.update(current_time, equity)
    
    if rm.is_halted:
        continue
    
    # SuperTrend check
    if current_time.minute != 0:
        continue
    if 'H1' not in dict_data[symbol] or current_time not in dict_data[symbol]['H1']:
        continue
    
    strat_data = dict_precalc[symbol]['H1']
    if s.name not in strat_data or current_time not in strat_data[s.name]:
        continue
    
    row_st = strat_data[s.name][current_time]
    if row_st['signal'] == 0:
        continue
    
    # Calculate risk
    if row_st['signal'] == 1:
        risk_dist = price - row_st['sl']
    else:
        risk_dist = row_st['sl'] - price
    
    if risk_dist <= 0 or pd.isna(risk_dist):
        print(f"  INVALID risk_dist={risk_dist} at {current_time} (signal={row_st['signal']}, price={price}, sl={row_st['sl']})")
        continue
    
    print(f"  *** TRADE EXECUTED at {current_time}: signal={row_st['signal']}, price={price:.2f}, sl={row_st['sl']:.2f}, tp={row_st['tp']:.2f}")

print(f"\nFinal equity: ${equity:.2f}")
print(f"Halt status: {rm.is_halted}")
