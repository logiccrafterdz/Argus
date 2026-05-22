from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from indicators import RSI
from market_structure import get_swing_highs, get_swing_lows

class HiddenDivergence(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="Hidden_Divergence",
            category="Divergence",
            regime_mask=1 | 16, # TREND | REVERSAL
            session_mask=7
        )
        self.lookback = 40
        
    def prepare_data(self, df):
        df['rsi'] = RSI(df['close'], 14)
        
        is_high = get_swing_highs(df, 3)
        is_low = get_swing_lows(df, 3)
        self._add_atr_col(df)
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        for i in range(self.lookback, len(df)):
            signal = 0
            sl = np.nan
            tp = np.nan
            
            close1 = df['close'].iloc[i-1]
            rsi1 = df['rsi'].iloc[i-1]
            
            # Simple Hidden Bullish Div: price makes higher low, RSI makes lower low
            # Meaning trend is up but momentum indicator reset
            if is_low[i-1]:
                prev_low_idx = next((j for j in range(i-2, i-self.lookback, -1) if is_low[j]), None)
                if prev_low_idx is not None:
                    prev_low_price = df['low'].iloc[prev_low_idx]
                    prev_rsi = df['rsi'].iloc[prev_low_idx]
                    curr_low_price = df['low'].iloc[i-1]
                    
                    if curr_low_price > prev_low_price and rsi1 < prev_rsi:
                        signal = 1
                        sl = curr_low_price - self._atr_buf(df, i-1, 1.0)
                        tp = close1 + self._atr_buf(df, i-1, 2.0)
                        
            # Hidden Bearish Div: price makes lower high, RSI makes higher high
            elif is_high[i-1]:
                prev_high_idx = next((j for j in range(i-2, i-self.lookback, -1) if is_high[j]), None)
                if prev_high_idx is not None:
                    prev_high_price = df['high'].iloc[prev_high_idx]
                    prev_rsi = df['rsi'].iloc[prev_high_idx]
                    curr_high_price = df['high'].iloc[i-1]
                    
                    if curr_high_price < prev_high_price and rsi1 > prev_rsi:
                        signal = -1
                        sl = curr_high_price + self._atr_buf(df, i-1, 1.0)
                        tp = close1 - self._atr_buf(df, i-1, 2.0)

            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        pad = [0] * self.lookback
        pad_nan = [np.nan] * self.lookback
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df
