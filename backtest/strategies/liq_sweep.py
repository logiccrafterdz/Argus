from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from market_structure import get_liquidity_pools, precompute_swings
import numpy as np

class LiquiditySweepFVG(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="Liquidity Sweep FVG",
            category="Smart Money",
            regime_mask=1 | 4 | 16, # TREND | EXPANSION | REVERSAL
            session_mask=7 # SESSION_ALL
        )
        self.lookback = 50
        self.threshold_multiplier = 0.5
        
    def prepare_data(self, df):
        # Precompute swing arrays once
        swing_highs, swing_lows = precompute_swings(df)
        self._add_atr_col(df)
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        start_idx = self.lookback
        
        for i in range(start_idx, len(df)):
            close1 = df['close'].iloc[i-1]
            low1 = df['low'].iloc[i-1]
            high1 = df['high'].iloc[i-1]
            
            # Simple FVG detection (Fair Value Gap)
            # Bullish FVG: low of i-1 > high of i-3, with i-2 being a strong green candle
            fvg_bullish = False
            fvg_bearish = False
            
            if df['low'].iloc[i-1] > df['high'].iloc[i-3] and df['close'].iloc[i-2] > df['open'].iloc[i-2]:
                fvg_bullish = True
                fvg_price_low = df['high'].iloc[i-3]
                
            if df['high'].iloc[i-1] < df['low'].iloc[i-3] and df['close'].iloc[i-2] < df['open'].iloc[i-2]:
                fvg_bearish = True
                fvg_price_high = df['low'].iloc[i-3]

            liq_high, liq_low = get_liquidity_pools(df, i, self.lookback, 2, self._atr_buf(df, i, self.threshold_multiplier), swing_highs, swing_lows)
            
            signal = 0
            sl = np.nan
            tp = np.nan
            
            if fvg_bullish and not np.isnan(liq_low):
                # Sweep low, then FVG formed
                if df['low'].iloc[i-2] < liq_low:
                    signal = 1
                    sl = df['low'].iloc[i-2] - self._atr_buf(df, i-1)
                    tp = df['close'].iloc[i-1] + (df['close'].iloc[i-1] - sl) * 2.5
            elif fvg_bearish and not np.isnan(liq_high):
                # Sweep high, then FVG formed
                if df['high'].iloc[i-2] > liq_high:
                    signal = -1
                    sl = df['high'].iloc[i-2] + self._atr_buf(df, i-1)
                    tp = df['close'].iloc[i-1] - (sl - df['close'].iloc[i-1]) * 2.5

            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        pad = [0] * start_idx
        pad_nan = [np.nan] * start_idx
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df
