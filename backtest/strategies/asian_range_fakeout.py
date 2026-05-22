from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

class AsianRangeFakeout(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="Asian_Range_Fakeout",
            category="Session",
            regime_mask=2 | 8 | 16, # RANGE | COMPRESSION | REVERSAL
            session_mask=2 # LONDON
        )
        
    def prepare_data(self, df):
        self._add_atr_col(df)
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        asian_high = np.nan
        asian_low = np.nan
        in_asia = False
        traded_today = False
        fakeout_up = False
        fakeout_dn = False
        
        for i in range(len(df)):
            t = df['time'].iloc[i]
            
            # Asian Session roughly 00:00 to 08:00
            if t.hour == 0 and t.minute == 0:
                asian_high = df['high'].iloc[i]
                asian_low = df['low'].iloc[i]
                in_asia = True
                traded_today = False
                fakeout_up = False
                fakeout_dn = False
            elif 0 <= t.hour < 8 and in_asia:
                asian_high = max(asian_high, df['high'].iloc[i])
                asian_low = min(asian_low, df['low'].iloc[i])
            elif t.hour == 8 and t.minute == 0:
                in_asia = False
                
            signal = 0
            sl = np.nan
            tp = np.nan
            
            # London Session 08:00 to 16:00
            if not in_asia and 8 <= t.hour < 16 and not traded_today and not np.isnan(asian_high):
                close1 = df['close'].iloc[i-1]
                high1 = df['high'].iloc[i-1]
                low1 = df['low'].iloc[i-1]
                
                # Detect Fakeout (Sweep of Asian range then close back inside)
                if high1 > asian_high and close1 < asian_high:
                    fakeout_up = True
                if low1 < asian_low and close1 > asian_low:
                    fakeout_dn = True
                    
                # Enter on fakeout
                if fakeout_up and close1 < asian_high - self._atr_buf(df, i-1):
                    signal = -1
                    sl = asian_high + self._atr_buf(df, i-1)
                    tp = asian_low
                    traded_today = True
                elif fakeout_dn and close1 > asian_low + self._atr_buf(df, i-1):
                    signal = 1
                    sl = asian_low - self._atr_buf(df, i-1)
                    tp = asian_high
                    traded_today = True

            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        df['signal'] = signals
        df['sl'] = sl_prices
        df['tp'] = tp_prices
        
        return df
