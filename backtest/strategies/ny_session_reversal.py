from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

class NYSessionReversal(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="NY_Session_Reversal",
            category="Session",
            regime_mask=2 | 16, # RANGE | REVERSAL
            session_mask=4 # NY
        )
        self.disable_breakeven = True
        
    def prepare_data(self, df):
        self._add_atr_col(df)
        signals = []
        sl_prices = []
        tp_prices = []
        
        london_high = np.nan
        london_low = np.nan
        in_london = False
        traded_today = False
        
        for i in range(len(df)):
            t = df['time'].iloc[i]
            
            # London Session 08:00 to 13:00 (before NY)
            if t.hour == 8 and t.minute == 0:
                london_high = df['high'].iloc[i]
                london_low = df['low'].iloc[i]
                in_london = True
                traded_today = False
            elif 8 <= t.hour < 13 and in_london:
                london_high = max(london_high, df['high'].iloc[i])
                london_low = min(london_low, df['low'].iloc[i])
            elif t.hour == 13 and t.minute == 0:
                in_london = False
                
            signal = 0
            sl = np.nan
            tp = np.nan
            
            # NY Session 13:00 to 17:00
            if not in_london and 13 <= t.hour < 17 and not traded_today and not np.isnan(london_high):
                close1 = df['close'].iloc[i-1]
                high1 = df['high'].iloc[i-1]
                low1 = df['low'].iloc[i-1]
                
                # NY fakeout of London High/Low with fixed R:R
                if high1 > london_high and close1 < london_high - self._atr_buf(df, i-1):
                    signal = -1
                    sl = close1 + self._atr_buf(df, i-1, 2.0)
                    tp = close1 - self._atr_buf(df, i-1, 14.0)
                    traded_today = True
                elif low1 < london_low and close1 > london_low + self._atr_buf(df, i-1):
                    signal = 1
                    sl = close1 - self._atr_buf(df, i-1, 2.0)
                    tp = close1 + self._atr_buf(df, i-1, 14.0)
                    traded_today = True

            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        df['signal'] = signals
        df['sl'] = sl_prices
        df['tp'] = tp_prices
        
        return df
