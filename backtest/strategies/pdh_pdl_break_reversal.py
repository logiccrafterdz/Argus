from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

class PDHPDLBreakReversal(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="PDH_PDL_BreakReversal",
            category="Session",
            regime_mask=4 | 16, # EXPANSION | REVERSAL
            session_mask=7
        )
        
    def prepare_data(self, df):
        # We need daily high/low. Since df is intraday, we groupby date.
        df['date'] = df['time'].apply(lambda x: x.date())
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        # Calculate daily high/low iteratively to avoid lookahead
        daily_highs = {}
        daily_lows = {}
        
        for i in range(len(df)):
            t = df['time'].iloc[i]
            d = t.date()
            
            if d not in daily_highs:
                daily_highs[d] = df['high'].iloc[i]
                daily_lows[d] = df['low'].iloc[i]
            else:
                daily_highs[d] = max(daily_highs[d], df['high'].iloc[i])
                daily_lows[d] = min(daily_lows[d], df['low'].iloc[i])
                
            signal = 0
            sl = np.nan
            tp = np.nan
            
            if i > 50:
                prev_d = df['time'].iloc[i-1].date()
                curr_d = df['time'].iloc[i].date()
                
                # Find previous day
                unique_dates = list(daily_highs.keys())
                if curr_d in unique_dates:
                    curr_idx = unique_dates.index(curr_d)
                    if curr_idx > 0:
                        pdh = daily_highs[unique_dates[curr_idx-1]]
                        pdl = daily_lows[unique_dates[curr_idx-1]]
                        
                        close1 = df['close'].iloc[i-1]
                        close2 = df['close'].iloc[i-2]
                        
                        buffer = 0.00050
                        
                        # Breakout of PDH
                        if close2 <= pdh and close1 > pdh + buffer:
                            signal = 1
                            sl = df['low'].iloc[i-3:i].min() - 0.00050
                            tp = close1 + (close1 - sl) * 1.5
                            
                        # Breakout of PDL
                        elif close2 >= pdl and close1 < pdl - buffer:
                            signal = -1
                            sl = df['high'].iloc[i-3:i].max() + 0.00050
                            tp = close1 - (sl - close1) * 1.5
                            
            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        df['signal'] = signals
        df['sl'] = sl_prices
        df['tp'] = tp_prices
        
        return df
