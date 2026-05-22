import pandas as pd
import numpy as np

df = pd.read_csv('backtest/data/EURUSD_H4.csv', parse_dates=['time'])
df.set_index('time', inplace=True)
eurusd_d1 = df.resample('D').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
print(f"eurusd_d1 shape: {eurusd_d1.shape}")

from backtest.indicators import ADX, MarketRegime

adx, plus_di, minus_di = ADX(eurusd_d1, 14)
print(f"adx shape: {adx.shape}")
print(f"plus_di shape: {plus_di.shape}")
print(f"minus_di shape: {minus_di.shape}")

regime = MarketRegime(eurusd_d1)
print(f"regime shape: {regime.shape}")
print(f"regime values: {np.unique(regime)}")
