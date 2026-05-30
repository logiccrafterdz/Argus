from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from indicators import BollingerBands, RSI, ADX
import numpy as np

class BollingerMeanReversion(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="Bollinger Mean Reversion",
            category="Mean Reversion",
            regime_mask=2 | 8, # REGIME_RANGE | REGIME_COMPRESSION
            session_mask=7 # SESSION_ALL
        )
        self.bb_period = 20
        self.bb_dev = 2.0
        self.rsi_period = 14
        self.disable_breakeven = True

    def prepare_data(self, df):
        upper, sma, lower = BollingerBands(df['close'], self.bb_period, self.bb_dev)
        df['bb_upper'] = upper
        df['bb_sma'] = sma
        df['bb_lower'] = lower
        df['rsi'] = RSI(df['close'], self.rsi_period)
        adx, _, _ = ADX(df, 14)
        df['adx'] = adx
        self._add_atr_col(df)
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        start_idx = max(self.bb_period, self.rsi_period)
        
        for i in range(start_idx, len(df)):
            close1 = df['close'].iloc[i-1]
            low1 = df['low'].iloc[i-1]
            high1 = df['high'].iloc[i-1]
            
            upper1 = df['bb_upper'].iloc[i-1]
            lower1 = df['bb_lower'].iloc[i-1]
            sma1 = df['bb_sma'].iloc[i-1]
            rsi1 = df['rsi'].iloc[i-1]
            
            adx1 = df['adx'].iloc[i-1]
            
            # Oversold and touching lower band (no strong trend)
            if low1 <= lower1 and rsi1 < 30 and close1 > lower1 and adx1 < 30:
                signals.append(1)
                sl = close1 - self._atr_buf(df, i-1, 2.0)
                tp = close1 + self._atr_buf(df, i-1, 4.0)
                sl_prices.append(sl)
                tp_prices.append(tp)
            # Overbought and touching upper band
            elif high1 >= upper1 and rsi1 > 70 and close1 < upper1 and adx1 < 30:
                signals.append(-1)
                sl = close1 + self._atr_buf(df, i-1, 2.0)
                tp = close1 - self._atr_buf(df, i-1, 4.0)
                sl_prices.append(sl)
                tp_prices.append(tp)
            else:
                signals.append(0)
                sl_prices.append(np.nan)
                tp_prices.append(np.nan)

        pad = [0] * start_idx
        pad_nan = [np.nan] * start_idx
        
        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices
        
        return df
