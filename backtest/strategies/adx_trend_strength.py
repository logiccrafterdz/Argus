from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from indicators import ADX, EMA

class ADXTrendStrength(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="ADX_TrendStrength",
            category="Trend Following",
            regime_mask=1, # TREND
            session_mask=7
        )
        
    def prepare_data(self, df):
        adx, pdi, mdi = ADX(df, 14)
        df['adx'] = adx
        df['pdi'] = pdi
        df['mdi'] = mdi
        df['ema'] = EMA(df['close'], 50)
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        for i in range(50, len(df)):
            signal = 0
            sl = np.nan
            tp = np.nan
            
            adx1 = df['adx'].iloc[i-1]
            pdi1 = df['pdi'].iloc[i-1]
            mdi1 = df['mdi'].iloc[i-1]
            
            pdi2 = df['pdi'].iloc[i-2]
            mdi2 = df['mdi'].iloc[i-2]
            
            close1 = df['close'].iloc[i-1]
            ema1 = df['ema'].iloc[i-1]
            
            # Trend is strong
            if adx1 > 25:
                # DI crossover
                if pdi1 > mdi1 and pdi2 <= mdi2 and close1 > ema1:
                    signal = 1
                    sl = df['low'].iloc[i-3:i].min() - 0.00050
                    tp = close1 + (close1 - sl) * 1.5
                elif mdi1 > pdi1 and mdi2 <= pdi2 and close1 < ema1:
                    signal = -1
                    sl = df['high'].iloc[i-3:i].max() + 0.00050
                    tp = close1 - (sl - close1) * 1.5

            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        pad = [0] * 50
        pad_nan = [np.nan] * 50
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df
