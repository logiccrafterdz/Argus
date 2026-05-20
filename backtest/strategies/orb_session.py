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
            regime_mask=4, # EXPANSION
            session_mask=2 | 4 # LONDON | NY
        )
        self.orb_duration_minutes = 30
        
    def prepare_data(self, df):
        signals = []
        sl_prices = []
        tp_prices = []
        
        # simplified ORB logic for M15: track first 2 bars of London (8am) or NY (13pm)
        orb_high = np.nan
        orb_low = np.nan
        in_orb = False
        traded_today = False
        
        for i in range(len(df)):
            t = df.index[i]
            
            if t.hour == 8 and t.minute == 0:
                orb_high = df['high'].iloc[i]
                orb_low = df['low'].iloc[i]
                in_orb = True
                traded_today = False
            elif t.hour == 8 and t.minute == 15 and in_orb:
                orb_high = max(orb_high, df['high'].iloc[i])
                orb_low = min(orb_low, df['low'].iloc[i])
                in_orb = False
                
            elif t.hour == 13 and t.minute == 0:
                orb_high = df['high'].iloc[i]
                orb_low = df['low'].iloc[i]
                in_orb = True
                traded_today = False
            elif t.hour == 13 and t.minute == 15 and in_orb:
                orb_high = max(orb_high, df['high'].iloc[i])
                orb_low = min(orb_low, df['low'].iloc[i])
                in_orb = False
                
            signal = 0
            sl = np.nan
            tp = np.nan
            
            if not in_orb and not traded_today and not np.isnan(orb_high):
                close = df['close'].iloc[i]
                if close > orb_high:
                    signal = 1
                    sl = orb_low
                    tp = close + (close - sl) * 2
                    traded_today = True
                elif close < orb_low:
                    signal = -1
                    sl = orb_high
                    tp = close - (sl - close) * 2
                    traded_today = True
                    
            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        df['signal'] = signals
        df['sl'] = sl_prices
        df['tp'] = tp_prices
        
        return df
