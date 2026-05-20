from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from indicators import EMA
from market_structure import is_bullish_structure, is_bearish_structure
import numpy as np

class TrendPullback(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="TrendPullback",
            category="Trend Following",
            regime_mask=1 | 4, # REGIME_TREND | REGIME_EXPANSION
            session_mask=7 # SESSION_ALL
        )
        self.fast_ema_period = 50
        self.slow_ema_period = 200
        self.market_structure_period = 30
        self.tp_multiplier = 2.0

    def prepare_data(self, df):
        df['fast_ema'] = EMA(df['close'], self.fast_ema_period)
        df['slow_ema'] = EMA(df['close'], self.slow_ema_period)
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        # We start from the index where EMAs are stable
        start_idx = self.slow_ema_period
        
        for i in range(start_idx, len(df)):
            # Market Analysis (2-Bar Logic) -> i corresponds to current bar, i-1 is bar 1, i-2 is bar 2
            bar1_close = df['close'].iloc[i-1]
            bar2_high = df['high'].iloc[i-2]
            bar2_low = df['low'].iloc[i-2]
            
            fast_ema_1 = df['fast_ema'].iloc[i-1]
            slow_ema_1 = df['slow_ema'].iloc[i-1]
            slow_ema_2 = df['slow_ema'].iloc[i-2]
            fast_ema_2 = df['fast_ema'].iloc[i-2]
            
            ema_bias_up = (fast_ema_1 > slow_ema_1) and (slow_ema_1 > slow_ema_2)
            ema_bias_dn = (fast_ema_1 < slow_ema_1) and (slow_ema_1 < slow_ema_2)
            
            structure_up = is_bullish_structure(df, i, self.market_structure_period)
            structure_dn = is_bearish_structure(df, i, self.market_structure_period)
            
            is_uptrend = ema_bias_up and structure_up
            is_downtrend = ema_bias_dn and structure_dn
            
            bull_pullback = is_uptrend and (df['low'].iloc[i-2] <= fast_ema_2)
            bear_pullback = is_downtrend and (df['high'].iloc[i-2] >= fast_ema_2)
            
            bull_trigger = bull_pullback and (bar1_close > bar2_high)
            bear_trigger = bear_pullback and (bar1_close < bar2_low)
            
            if bull_trigger:
                signals.append(1)
                sl = df['low'].iloc[i-1] - 0.00050 # 5 pips approx for FX
                tp = df['close'].iloc[i-1] + ((df['close'].iloc[i-1] - sl) * self.tp_multiplier)
                sl_prices.append(sl)
                tp_prices.append(tp)
            elif bear_trigger:
                signals.append(-1)
                sl = df['high'].iloc[i-1] + 0.00050
                tp = df['close'].iloc[i-1] - ((sl - df['close'].iloc[i-1]) * self.tp_multiplier)
                sl_prices.append(sl)
                tp_prices.append(tp)
            else:
                signals.append(0)
                sl_prices.append(np.nan)
                tp_prices.append(np.nan)
                
        # Pad beginning
        pad = [0] * start_idx
        pad_nan = [np.nan] * start_idx
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df
