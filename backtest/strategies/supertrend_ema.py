from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from indicators import SuperTrend, EMA

class SuperTrendEMA(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="SuperTrend_EMA",
            category="Trend Following",
            regime_mask=1 | 4, # TREND | EXPANSION
            session_mask=7
        )
        
    def prepare_data(self, df):
        supertrend, direction = SuperTrend(df, period=10, multiplier=3)
        df['st_dir'] = direction
        df['st_val'] = supertrend
        df['ema'] = EMA(df['close'], 50)
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        for i in range(50, len(df)):
            signal = 0
            sl = np.nan
            tp = np.nan
            
            dir1 = df['st_dir'].iloc[i-1]
            dir2 = df['st_dir'].iloc[i-2]
            close1 = df['close'].iloc[i-1]
            ema1 = df['ema'].iloc[i-1]
            st_val = df['st_val'].iloc[i-1]
            
            # Supertrend flips direction in agreement with EMA
            if dir1 == 1 and dir2 == -1 and close1 > ema1:
                signal = 1
                sl = st_val - 0.00050
                tp = close1 + (close1 - sl) * 1.5
            elif dir1 == -1 and dir2 == 1 and close1 < ema1:
                signal = -1
                sl = st_val + 0.00050
                tp = close1 - (sl - close1) * 1.5

            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        pad = [0] * 50
        pad_nan = [np.nan] * 50
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df
