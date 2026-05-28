from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd

class ICTKillzoneMacro(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="ICT_Killzone_Macro",
            category="Liquidity Hunting",
            regime_mask=1 | 4 | 16, # TREND | EXPANSION | REVERSAL
            session_mask=2 | 4 # SESSION_LONDON | SESSION_NY
        )
        self.killzone_start_hour = 7
        self.killzone_end_hour = 9
        self.ref_lookback_hours = 4
        self.sl_atr = 2.0
        self.tp_atr = 16.0
        self.disable_breakeven = True

    def prepare_data(self, df):
        signals = []
        sl_prices = []
        tp_prices = []
        
        start_idx = self.ref_lookback_hours * 4 # roughly for M15
        self._add_atr_col(df)
        
        for i in range(start_idx, len(df)):
            current_time = df['time'].iloc[i]
            hour = current_time.hour
            minute = current_time.minute
            
            # Simplified logic for calculating Reference High/Low before Killzone
            if hour == self.killzone_start_hour and minute == 0:
                # Calculate Liq High/Low from past X hours
                past_data = df.iloc[i - (self.ref_lookback_hours * 4) : i]
                self.liq_high = past_data['high'].max()
                self.liq_low = past_data['low'].min()
                self.sweep_buy_triggered = False
                self.sweep_sell_triggered = False

            signal = 0
            sl = np.nan
            tp = np.nan
            
            # Watch Sweep during Killzone
            if self.killzone_start_hour <= hour < self.killzone_end_hour and hasattr(self, 'liq_high'):
                close1 = df['close'].iloc[i-1]
                low1 = df['low'].iloc[i-1]
                high1 = df['high'].iloc[i-1]
                
                # Bullish Sweep
                buffer = self._atr_buf(df, i-1, 0.2)
                if low1 < self.liq_low - buffer and close1 > self.liq_low and not self.sweep_buy_triggered:
                    signal = 1
                    sl = close1 - self._atr_buf(df, i-1, self.sl_atr)
                    tp = close1 + self._atr_buf(df, i-1, self.tp_atr)
                    self.sweep_buy_triggered = True

                # Bearish Sweep
                elif high1 > self.liq_high + buffer and close1 < self.liq_high and not self.sweep_sell_triggered:
                    signal = -1
                    sl = close1 + self._atr_buf(df, i-1, self.sl_atr)
                    tp = close1 - self._atr_buf(df, i-1, self.tp_atr)
                    self.sweep_sell_triggered = True

            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        pad = [0] * start_idx
        pad_nan = [np.nan] * start_idx
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df
