from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from market_structure import get_liquidity_pools, precompute_swings

class LiquiditySweepBreakout(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="Liquidity_Sweep_Breakout",
            category="Smart Money",
            regime_mask=1 | 4 | 16, # TREND | EXPANSION | REVERSAL
            session_mask=7
        )
        self.lookback = 50
        
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
            
            liq_high, liq_low = get_liquidity_pools(df, i, self.lookback, 2, self._atr_buf(df, i, 0.5), swing_highs, swing_lows)
            
            signal = 0
            sl = np.nan
            tp = np.nan
            
            if not np.isnan(liq_low) and df['low'].iloc[i-2] < liq_low and close1 > liq_low:
                # Swept liquidity and closed back above, now check MSB (Market Structure Break)
                # Simple MSB: close > recent swing high
                recent_high = df['high'].iloc[i-10:i-1].max()
                if close1 > recent_high:
                    signal = 1
                    sl = close1 - self._atr_buf(df, i-1, 1.0)
                    tp = close1 + self._atr_buf(df, i-1, 2.0)
                    
            elif not np.isnan(liq_high) and df['high'].iloc[i-2] > liq_high and close1 < liq_high:
                recent_low = df['low'].iloc[i-10:i-1].min()
                if close1 < recent_low:
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
