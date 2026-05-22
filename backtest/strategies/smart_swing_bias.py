from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from market_structure import is_bullish_structure, is_bearish_structure, precompute_swings

class SmartSwingBias(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="Smart_Swing_Bias",
            category="Trend Following",
            regime_mask=1, # TREND
            session_mask=7
        )
        self.lookback = 40
        
    def prepare_data(self, df):
        # Precompute swing arrays once
        swing_highs, swing_lows = precompute_swings(df)
        
        self._add_atr_col(df)
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        start_idx = self.lookback
        
        for i in range(start_idx, len(df)):
            signal = 0
            sl = np.nan
            tp = np.nan
            
            # Simple Multi-TF approximation: check structure on large lookback and small lookback
            bull_htf = is_bullish_structure(df, i, self.lookback*2, swing_lows=swing_lows)
            bull_ltf = is_bullish_structure(df, i, self.lookback, swing_lows=swing_lows)
            
            bear_htf = is_bearish_structure(df, i, self.lookback*2, swing_highs=swing_highs)
            bear_ltf = is_bearish_structure(df, i, self.lookback, swing_highs=swing_highs)
            
            close1 = df['close'].iloc[i-1]
            close2 = df['close'].iloc[i-2]
            
            if bull_htf and bull_ltf and close2 < close1:
                signal = 1
                sl = df['low'].iloc[i-5:i].min() - self._atr_buf(df, i-1, 1.0)
                tp = close1 + (close1 - sl) * 2.0
            elif bear_htf and bear_ltf and close2 > close1:
                signal = -1
                sl = df['high'].iloc[i-5:i].max() + self._atr_buf(df, i-1, 1.0)
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
