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
        self.disable_breakeven = True
        
    def prepare_data(self, df):
        adx, pdi, mdi = ADX(df, 14)
        df['adx'] = adx
        df['pdi'] = pdi
        df['mdi'] = mdi
        df['ema'] = EMA(df['close'], 50)
        self._add_atr_col(df)
        
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
            
            close1 = df['close'].iloc[i-1]
            ema1 = df['ema'].iloc[i-1]
            
            # Strong trend with DI bias (crossover in last 3 bars or strong DI spread)
            if adx1 > 25:
                di_spread = pdi1 - mdi1
                if di_spread > 10 and close1 > ema1:
                    signal = 1
                    sl = close1 - self._atr_buf(df, i-1, 2.5)
                    tp = close1 + self._atr_buf(df, i-1, 8.0)
                elif di_spread < -10 and close1 < ema1:
                    signal = -1
                    sl = close1 + self._atr_buf(df, i-1, 2.5)
                    tp = close1 - self._atr_buf(df, i-1, 8.0)
            
            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)
        
        pad = [0] * 50
        pad_nan = [np.nan] * 50
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df