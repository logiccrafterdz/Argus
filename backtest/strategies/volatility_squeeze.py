from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from indicators import BollingerBands, KeltnerChannels, EMA

class VolatilitySqueeze(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="Volatility_Squeeze",
            category="Breakout",
            regime_mask=4 | 8, # EXPANSION | COMPRESSION
            session_mask=7
        )
        
    def prepare_data(self, df):
        bb_upper, _, bb_lower = BollingerBands(df['close'], period=20, std_dev=2.0)
        kc_upper, _, kc_lower = KeltnerChannels(df, period=20, atr_period=10, multiplier=1.5)
        
        df['ema'] = EMA(df['close'], 20)
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        in_squeeze = False
        
        for i in range(20, len(df)):
            signal = 0
            sl = np.nan
            tp = np.nan
            
            # Squeeze is on when BB is inside Keltner Channels
            is_squeeze = bb_upper.iloc[i-1] < kc_upper.iloc[i-1] and bb_lower.iloc[i-1] > kc_lower.iloc[i-1]
            
            if is_squeeze:
                in_squeeze = True
            elif in_squeeze and not is_squeeze:
                # Squeeze fired (BB expanded outside Keltner)
                in_squeeze = False
                
                close1 = df['close'].iloc[i-1]
                ema = df['ema'].iloc[i-1]
                
                if close1 > ema:
                    signal = 1
                    sl = df['low'].iloc[i-2:i].min() - 0.00050
                    tp = close1 + (close1 - sl) * 2.0
                elif close1 < ema:
                    signal = -1
                    sl = df['high'].iloc[i-2:i].max() + 0.00050
                    tp = close1 - (sl - close1) * 2.0

            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        pad = [0] * 20
        pad_nan = [np.nan] * 20
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df
