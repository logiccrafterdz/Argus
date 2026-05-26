from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from indicators import EMA

class SRBreakoutRetest(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="SR_Breakout_Retest",
            category="Breakout",
            regime_mask=1 | 2 | 4, # TREND | RANGE | EXPANSION
            session_mask=7
        )
        self.lookback = 50
        self.disable_breakeven = True

    def prepare_data(self, df):
        signals = []
        sl_prices = []
        tp_prices = []
        
        start_idx = self.lookback
        
        self._add_atr_col(df)
        df['ema200'] = EMA(df['close'], 200)
        
        for i in range(start_idx, len(df)):
            close1 = df['close'].iloc[i-1]
            
            recent_high = df['high'].iloc[i-self.lookback:i-1].max()
            recent_low = df['low'].iloc[i-self.lookback:i-1].min()
            
            signal = 0
            sl = np.nan
            tp = np.nan
            
            ema200 = df['ema200'].iloc[i-1]
            
            # Breakout: price closed above recent high, confirm above EMA200
            if close1 > recent_high and not np.isnan(ema200) and close1 > ema200:
                signal = 1
                sl = close1 - self._atr_buf(df, i-1, 2.0)
                tp = close1 + self._atr_buf(df, i-1, 14.0)
            elif close1 < recent_low and not np.isnan(ema200) and close1 < ema200:
                signal = -1
                sl = close1 + self._atr_buf(df, i-1, 2.0)
                tp = close1 - self._atr_buf(df, i-1, 14.0)
                
            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        pad = [0] * start_idx
        pad_nan = [np.nan] * start_idx
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df
