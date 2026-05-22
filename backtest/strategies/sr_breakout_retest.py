from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

class SRBreakoutRetest(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="SR_Breakout_Retest",
            category="Breakout",
            regime_mask=1 | 2 | 4, # TREND | RANGE | EXPANSION
            session_mask=7
        )
        self.lookback = 40
        self.buffer = 0.00050

    def prepare_data(self, df):
        signals = []
        sl_prices = []
        tp_prices = []
        
        start_idx = self.lookback
        
        self._add_atr_col(df)
        
        for i in range(start_idx, len(df)):
            close1 = df['close'].iloc[i-1]
            close2 = df['close'].iloc[i-2]
            
            recent_high = df['high'].iloc[i-self.lookback:i-1].max()
            recent_low = df['low'].iloc[i-self.lookback:i-1].min()
            
            signal = 0
            sl = np.nan
            tp = np.nan
            
            # Breakout and Retest (simplified)
            # Bullish: previous candle closed above recent high, current candle pulls back
            if close2 > recent_high and close1 <= recent_high + self.buffer and close1 >= recent_high - self.buffer:
                signal = 1
                sl = close1 - self._atr_buf(df, i-1, 1.0)
                tp = close1 + self._atr_buf(df, i-1, 2.0)
                
            # Bearish
            elif close2 < recent_low and close1 >= recent_low - self.buffer and close1 <= recent_low + self.buffer:
                signal = -1
                sl = close1 + self._atr_buf(df, i-1, 1.0)
                tp = close1 - self._atr_buf(df, i-1, 2.0)
                
            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        pad = [0] * start_idx
        pad_nan = [np.nan] * start_idx
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df
