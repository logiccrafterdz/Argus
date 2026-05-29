from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from market_structure import get_swing_highs, get_swing_lows

class AVWAPConfluence(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="AVWAP_Confluence",
            category="Institutional",
            regime_mask=1 | 16, # TREND | REVERSAL
            session_mask=7
        )
        self.disable_breakeven = True
        
    def prepare_data(self, df):
        signals = []
        sl_prices = []
        tp_prices = []
        
        is_high = get_swing_highs(df, 10)
        is_low = get_swing_lows(df, 10)
        self._add_atr_col(df)
        
        # Simplified Anchored VWAP: reset on significant swing high/low
        avwap = np.nan
        cum_vol = 0
        cum_vol_price = 0
        
        for i in range(len(df)):
            signal = 0
            sl = np.nan
            tp = np.nan
            
            if i > 0 and (is_high[i-1] or is_low[i-1]):
                # Anchor VWAP here
                avwap = df['close'].iloc[i-1]
                cum_vol = df['tick_volume'].iloc[i-1]
                tp_price = (df['high'].iloc[i-1] + df['low'].iloc[i-1] + df['close'].iloc[i-1]) / 3
                cum_vol_price = tp_price * cum_vol
            elif not np.isnan(avwap):
                vol = df['tick_volume'].iloc[i-1]
                tp_price = (df['high'].iloc[i-1] + df['low'].iloc[i-1] + df['close'].iloc[i-1]) / 3
                cum_vol += vol
                cum_vol_price += tp_price * vol
                avwap = cum_vol_price / cum_vol
                
                close1 = df['close'].iloc[i-1]
                close2 = df['close'].iloc[i-2]
                
                # Bounce off AVWAP
                buffer = self._atr_buf(df, i-1, 0.5)
                if close2 < avwap and close1 > avwap + buffer:
                    signal = 1
                    sl = close1 - self._atr_buf(df, i-1, 2.0)
                    tp = close1 + self._atr_buf(df, i-1, 7.0)
                elif close2 > avwap and close1 < avwap - buffer:
                    signal = -1
                    sl = close1 + self._atr_buf(df, i-1, 2.0)
                    tp = close1 - self._atr_buf(df, i-1, 7.0)
                    
            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        df['signal'] = signals
        df['sl'] = sl_prices
        df['tp'] = tp_prices
        
        return df
