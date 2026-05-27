from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from indicators import DonchianChannels, EMA

class DonchianBreakout(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="Donchian_Breakout",
            category="Breakout",
            regime_mask=1 | 2 | 4, # TREND | RANGE | EXPANSION
            session_mask=7
        )
        self.disable_breakeven = True
        
    def prepare_data(self, df):
        upper, middle, lower = DonchianChannels(df, period=10)
        df['dc_upper'] = upper
        df['dc_lower'] = lower
        df['ema'] = EMA(df['close'], 50)
        self._add_atr_col(df)
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        for i in range(60, len(df)):
            signal = 0
            sl = np.nan
            tp = np.nan
            
            high1 = df['high'].iloc[i-1]
            low1 = df['low'].iloc[i-1]
            close1 = df['close'].iloc[i-1]
            ema1 = df['ema'].iloc[i-1]
            dc_upper2 = df['dc_upper'].iloc[i-2]
            dc_lower2 = df['dc_lower'].iloc[i-2]
            atr1 = self._atr_buf(df, i-1, 1.0)
            
            # Breakout above DC upper with EMA50 trend filter + slope
            if close1 > dc_upper2 and ema1 > df['ema'].iloc[i-5] and close1 > ema1:
                signal = 1
                sl = min(low1, close1 - atr1 * 2.0)
                tp = close1 + atr1 * 8.0
            # Breakout below DC lower with EMA50 trend filter + slope
            elif close1 < dc_lower2 and ema1 < df['ema'].iloc[i-5] and close1 < ema1:
                signal = -1
                sl = max(high1, close1 + atr1 * 2.0)
                tp = close1 - atr1 * 8.0
            
            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)
        
        pad = [0] * 60
        pad_nan = [np.nan] * 60
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df