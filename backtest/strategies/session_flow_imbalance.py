from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

class SessionFlowImbalance(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="Session_Flow_Imbalance",
            category="Smart Money",
            regime_mask=1 | 2 | 4 | 16, # Operates in most regimes, session driven
            session_mask=2 | 4 # LONDON | NEWYORK
        )
        self.disable_breakeven = True
        
    def prepare_data(self, df):
        import pandas as pd
        if 'time' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['time']):
            df['time'] = pd.to_datetime(df['time'])
        
        self._add_atr_col(df)
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        asian_high = np.nan
        asian_low = np.nan
        asian_start_idx = -1
        last_signal_day = None
        
        for i in range(20, len(df)):
            signal = 0
            sl = np.nan
            tp = np.nan
            
            # Assuming df index is datetime. If not, we need a 'time' column.
            t1 = df['time'].iloc[i-1]
            t2 = df['time'].iloc[i-2] if i > 1 else t1
            
            close1 = df['close'].iloc[i-1]
            high1 = df['high'].iloc[i-1]
            low1 = df['low'].iloc[i-1]
            atr1 = self._atr_buf(df, i-1, 1.0)
            
            # Asian Session: 00:00 to 08:00
            if t1.hour == 0 and t2.hour != 0:
                asian_start_idx = i-1
                asian_high = high1
                asian_low = low1
                
            if 0 <= t1.hour < 8 and asian_start_idx != -1:
                asian_high = max(asian_high, high1)
                asian_low = min(asian_low, low1)
                            # London Open Strategy Trigger (08:00 to 12:00)
            if 8 <= t1.hour < 12 and not np.isnan(asian_high) and last_signal_day != t1.date():
                asian_range = asian_high - asian_low
                
                # Case 1: Accumulation (Tight Asian Range) -> Expansion (Trend with Breakout)
                if asian_range < atr1 * 0.3:  # Only true accumulation
                    if close1 > asian_high: # Bullish Breakout
                        signal = 1
                        sl = asian_low
                        risk = close1 - sl
                        tp = close1 + risk * 3.0  # 1:3 R:R
                        last_signal_day = t1.date()
                    elif close1 < asian_low: # Bearish Breakout
                        signal = -1
                        sl = asian_high
                        risk = sl - close1
                        tp = close1 - risk * 3.0  # 1:3 R:R
                        last_signal_day = t1.date()
                        
                # Case 2: Exhaustion (Wide Asian Range) -> Mean Reversion (Fade the edges)
                elif asian_range > atr1 * 2.0:  # Massive exhaustion
                    if high1 > asian_high and close1 < asian_high: # Fakeout High
                        signal = -1
                        sl = high1 + atr1 * 0.5
                        risk = sl - close1
                        tp = close1 - risk * 4.0  # 1:4 R:R
                        last_signal_day = t1.date()
                    elif low1 < asian_low and close1 > asian_low: # Fakeout Low
                        signal = 1
                        sl = low1 - atr1 * 0.5
                        risk = close1 - sl
                        tp = close1 + risk * 4.0  # 1:4 R:R
                        last_signal_day = t1.date()

            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        pad = [0] * 20
        pad_nan = [np.nan] * 20
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df
