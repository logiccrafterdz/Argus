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
            regime_mask=1 | 2 | 4, # TREND | RANGE | EXPANSION
            session_mask=7
        )
        
    def prepare_data(self, df):
        supertrend, direction = SuperTrend(df, period=20, multiplier=4)
        df['st_dir'] = direction
        df['st_val'] = supertrend
        df['ema'] = EMA(df['close'], 100)
        
        self._add_atr_col(df)
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        for i in range(100, len(df)):
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
                sl = close1 - self._atr_buf(df, i-1, 1.0)
                tp = close1 + self._atr_buf(df, i-1, 3.0)
            elif dir1 == -1 and dir2 == 1 and close1 < ema1:
                signal = -1
                sl = close1 + self._atr_buf(df, i-1, 1.0)
                tp = close1 - self._atr_buf(df, i-1, 3.0)

            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        pad = [0] * 100
        pad_nan = [np.nan] * 100
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df
