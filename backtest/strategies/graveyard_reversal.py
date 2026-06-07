from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from market_structure import get_liquidity_pools, precompute_swings

class GraveyardReversal(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="Graveyard_Reversal",
            category="Smart Money",
            regime_mask=1 | 2 | 16, # TREND | RANGE | REVERSAL
            session_mask=7 # SESSION_ALL
        )
        self.lookback = 50
        self.vol_multiplier = 2.0  # Require 2x volume spike for genuine smart money sweep
        self.disable_breakeven = True
        
    def prepare_data(self, df):
        # Precompute swing arrays once
        swing_highs, swing_lows = precompute_swings(df)
        self._add_atr_col(df)
        
        df['vol_ma'] = df['tick_volume'].rolling(20).mean()
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        start_idx = max(self.lookback, 20)
        
        for i in range(start_idx, len(df)):
            close1 = df['close'].iloc[i-1]
            open1 = df['open'].iloc[i-1]
            high1 = df['high'].iloc[i-1]
            low1 = df['low'].iloc[i-1]
            vol1 = df['tick_volume'].iloc[i-1]
            vol_ma = df['vol_ma'].iloc[i-1]
            atr = self._atr_buf(df, i-1, 1.0)
            
            # Find liquidity pools established BEFORE the current bar
            liq_high, liq_low = get_liquidity_pools(
                df, i, 
                lookback=self.lookback, 
                radius=2, 
                threshold_points=atr*0.5, 
                swing_highs=swing_highs, 
                swing_lows=swing_lows
            )
            
            signal = 0
            sl = np.nan
            tp = np.nan
            
            # 1. Sweep of Liquidity High (Bearish Reversal Trap)
            if not np.isnan(liq_high):
                # Price pierced the liquidity high, but closed below it (and below its own open -> bearish candle)
                if high1 > liq_high and close1 < liq_high and close1 < open1:
                    # Institutional footprint: Did volume spike during this sweep?
                    if vol1 > self.vol_multiplier * vol_ma:
                        sl = high1 + atr * 0.5  # Tight SL above the sweep wick
                        risk = sl - close1
                        target = liq_low if not np.isnan(liq_low) else close1 - atr * 4.0
                        reward = close1 - target
                        if risk > 0 and reward / risk >= 3.0:
                            signal = -1
                            tp = target
            
            # 2. Sweep of Liquidity Low (Bullish Reversal Trap)
            if not np.isnan(liq_low):
                # Price pierced the liquidity low, but closed above it (and above its own open -> bullish candle)
                if low1 < liq_low and close1 > liq_low and close1 > open1:
                    # Institutional footprint: Did volume spike during this sweep?
                    if vol1 > self.vol_multiplier * vol_ma:
                        sl = low1 - atr * 0.5  # Tight SL below the sweep wick
                        risk = close1 - sl
                        target = liq_high if not np.isnan(liq_high) else close1 + atr * 4.0
                        reward = target - close1
                        if risk > 0 and reward / risk >= 3.0:
                            signal = 1
                            tp = target

            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        pad = [0] * start_idx
        pad_nan = [np.nan] * start_idx
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df
