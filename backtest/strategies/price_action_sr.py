from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from market_structure import get_swing_highs, get_swing_lows

class PriceActionSR(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="PriceAction_SR",
            category="Price Action",
            regime_mask=2 | 16, # RANGE | REVERSAL
            session_mask=7
        )
        self.lookback = 100
        
    def prepare_data(self, df):
        signals = []
        sl_prices = []
        tp_prices = []
        
        is_high = get_swing_highs(df, 3)
        is_low = get_swing_lows(df, 3)
        self._add_atr_col(df)
        
        start_idx = self.lookback
        
        for i in range(start_idx, len(df)):
            close1 = df['close'].iloc[i-1]
            
            # Find closest support and resistance
            recent_highs = [df['high'].iloc[j] for j in range(i-self.lookback, i-1) if is_high[j]]
            recent_lows = [df['low'].iloc[j] for j in range(i-self.lookback, i-1) if is_low[j]]
            
            signal = 0
            sl = np.nan
            tp = np.nan
            
            if recent_highs and recent_lows:
                res = min([h for h in recent_highs if h > close1], default=np.nan)
                sup = max([l for l in recent_lows if l < close1], default=np.nan)
                
                # Reversal off support with ATR buffer
                if not np.isnan(sup) and close1 <= sup + self._atr_buf(df, i-1, 0.5) and df['close'].iloc[i-1] > df['open'].iloc[i-1]:
                    signal = 1
                    sl = sup - self._atr_buf(df, i-1, 1.0)
                    tp = close1 + (close1 - sl) * 2.0
                    
                # Reversal off resistance with ATR buffer
                elif not np.isnan(res) and close1 >= res - self._atr_buf(df, i-1, 0.5) and df['close'].iloc[i-1] < df['open'].iloc[i-1]:
                    signal = -1
                    sl = res + self._atr_buf(df, i-1, 1.0)
                    tp = close1 - (sl - close1) * 2.0
                    
            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        pad = [0] * start_idx
        pad_nan = [np.nan] * start_idx
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df
