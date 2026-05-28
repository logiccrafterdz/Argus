from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

class ORBSession(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="ORB_Session",
            category="Breakout",
            regime_mask=1 | 4, # TREND | EXPANSION
            session_mask=2 | 4 # LONDON | NY
        )
        self.orb_duration_minutes = 15
        self.disable_breakeven = True
        
    def prepare_data(self, df):
        self._add_atr_col(df)
        signals = []
        sl_prices = []
        tp_prices = []
        
        # ORB logic for M15: track first 60 min of London (8:00-9:00) or NY (13:00-14:00)
        orb_high = np.nan
        orb_low = np.nan
        in_orb = False
        traded_today = False
        orb_end = {8: 9, 13: 14}
        
        for i in range(len(df)):
            t = df['time'].iloc[i]
            
            if t.hour in orb_end and t.minute == 0:
                orb_high = df['high'].iloc[i]
                orb_low = df['low'].iloc[i]
                in_orb = True
                traded_today = False
            elif in_orb and t.hour < orb_end.get(t.hour, t.hour):
                orb_high = max(orb_high, df['high'].iloc[i])
                orb_low = min(orb_low, df['low'].iloc[i])
            elif in_orb and t.hour >= orb_end.get(t.hour, t.hour):
                in_orb = False
                
            signal = 0
            sl = np.nan
            tp = np.nan
            
            if not in_orb and not traded_today and not np.isnan(orb_high) and i > 0:
                close = df['close'].iloc[i-1]
                if close > orb_high:
                    signal = 1
                    sl = close - self._atr_buf(df, i-1, 2.0)
                    tp = close + self._atr_buf(df, i-1, 4.0)
                    traded_today = True
                elif close < orb_low:
                    signal = -1
                    sl = close + self._atr_buf(df, i-1, 2.0)
                    tp = close - self._atr_buf(df, i-1, 4.0)
                    traded_today = True
                    
            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        df['signal'] = signals
        df['sl'] = sl_prices
        df['tp'] = tp_prices
        
        return df
