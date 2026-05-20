from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from market_structure import is_bullish_structure, is_bearish_structure

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
        signals = []
        sl_prices = []
        tp_prices = []
        
        start_idx = self.lookback
        
        for i in range(start_idx, len(df)):
            signal = 0
            sl = np.nan
            tp = np.nan
            
            # Simple Multi-TF approximation: check structure on large lookback and small lookback
            bull_htf = is_bullish_structure(df, i, self.lookback*2)
            bull_ltf = is_bullish_structure(df, i, self.lookback)
            
            bear_htf = is_bearish_structure(df, i, self.lookback*2)
            bear_ltf = is_bearish_structure(df, i, self.lookback)
            
            close1 = df['close'].iloc[i-1]
            close2 = df['close'].iloc[i-2]
            
            if bull_htf and bull_ltf and close2 < close1:
                signal = 1
                sl = df['low'].iloc[i-5:i].min() - 0.00100
                tp = close1 + (close1 - sl) * 2.0
            elif bear_htf and bear_ltf and close2 > close1:
                signal = -1
                sl = df['high'].iloc[i-5:i].max() + 0.00100
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
