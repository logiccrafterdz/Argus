from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from market_structure import get_swing_highs, get_swing_lows

class VWAPBreakoutHedge(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="VWAP_Breakout_Hedge",
            category="Institutional",
            regime_mask=1 | 16, # TREND | REVERSAL
            session_mask=7
        )
        self.disable_breakeven = True
        self.vol_multiplier = 1.5
        self.rr_ratio = 3.0
        
    def prepare_data(self, df):
        signals = []
        sl_prices = []
        tp_prices = []
        
        is_high = get_swing_highs(df, 10)
        is_low = get_swing_lows(df, 10)
        self._add_atr_col(df)
        df['vol_ma'] = df['tick_volume'].rolling(20).mean()
        
        # Simplified Anchored VWAP: reset on significant swing high/low
        avwap = np.nan
        cum_vol = 0
        cum_vol_price = 0
        
        for i in range(len(df)):
            signal = 0
            sl = np.nan
            tp = np.nan
            
            if i > 0 and (is_high[i-1] or is_low[i-1]):
                # Anchor VWAP here
                avwap = df['close'].iloc[i-1]
                cum_vol = df['tick_volume'].iloc[i-1]
                tp_price = (df['high'].iloc[i-1] + df['low'].iloc[i-1] + df['close'].iloc[i-1]) / 3
                cum_vol_price = tp_price * cum_vol
            elif not np.isnan(avwap):
                vol = df['tick_volume'].iloc[i-1]
                tp_price = (df['high'].iloc[i-1] + df['low'].iloc[i-1] + df['close'].iloc[i-1]) / 3
                cum_vol += vol
                cum_vol_price += tp_price * vol
                avwap = cum_vol_price / cum_vol
                
                close1 = df['close'].iloc[i-1]
                close2 = df['close'].iloc[i-2]
                high1 = df['high'].iloc[i-1]
                low1 = df['low'].iloc[i-1]
                vol1 = df['tick_volume'].iloc[i-1]
                vol_ma1 = df['vol_ma'].iloc[i-1]
                atr1 = self._atr_buf(df, i-1, 1.0)
                
                # Check for structural VWAP breakout with Volume Spike
                if vol1 > vol_ma1 * self.vol_multiplier:
                    # Bullish Breakout (From below to above)
                    if close2 < avwap and close1 > avwap + atr1 * 0.2:
                        sl = min(low1, avwap - atr1 * 0.5)  # SL below the breakout candle or VWAP
                        risk = close1 - sl
                        
                        # Bound risk distance to avoid extreme position sizing
                        if risk < atr1 * 1.0:
                            risk = atr1 * 1.0
                            sl = close1 - risk
                            
                        if atr1 * 1.0 <= risk <= atr1 * 4.0:
                            signal = 1
                            tp = close1 + risk * self.rr_ratio
                            
                    # Bearish Breakout (From above to below)
                    elif close2 > avwap and close1 < avwap - atr1 * 0.2:
                        sl = max(high1, avwap + atr1 * 0.5)  # SL above the breakout candle or VWAP
                        risk = sl - close1
                        
                        # Bound risk distance to avoid extreme position sizing
                        if risk < atr1 * 1.0:
                            risk = atr1 * 1.0
                            sl = close1 + risk
                            
                        if atr1 * 1.0 <= risk <= atr1 * 4.0:
                            signal = -1
                            tp = close1 - risk * self.rr_ratio
                    
            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        df['signal'] = signals
        df['sl'] = sl_prices
        df['tp'] = tp_prices
        
        return df
