from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from indicators import VWAP, EMA

class VWAPMultiBandRegime(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="VWAP_MultiBand_Regime",
            category="Institutional",
            regime_mask=1 | 2, # TREND | RANGE
            session_mask=7
        )
        self.disable_breakeven = True
        self.sl_atr = 2.0
        self.tp_atr = 14.0
        self.lookback_std = 20
        
    def prepare_data(self, df):
        df['vwap'] = VWAP(df)
        
        # Calculate standard deviation for bands
        # A simple rolling std for illustration since exact VWAP stdev requires volume-weighted variance
        df['vwap_std'] = df['close'].rolling(self.lookback_std).std()
        df['vwap_upper1'] = df['vwap'] + df['vwap_std']
        df['vwap_lower1'] = df['vwap'] - df['vwap_std']
        df['vwap_upper2'] = df['vwap'] + 2 * df['vwap_std']
        df['vwap_lower2'] = df['vwap'] - 2 * df['vwap_std']
        
        self._add_atr_col(df)
        df['ema200'] = EMA(df['close'], 200)
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        for i in range(len(df)):
            signal = 0
            sl = np.nan
            tp = np.nan
            
            if i > self.lookback_std + 1:
                close1 = df['close'].iloc[i-1]
                close2 = df['close'].iloc[i-2]
                vwap_lower2 = df['vwap_lower2'].iloc[i-1]
                vwap_upper2 = df['vwap_upper2'].iloc[i-1]
                ema200 = df['ema200'].iloc[i-1]
                
                # Reversal from 2nd VWAP band, in direction of major trend
                if close2 < df['vwap_lower2'].iloc[i-2] and close1 > vwap_lower2 and not np.isnan(ema200) and close1 > ema200:
                    signal = 1
                    sl = close1 - self._atr_buf(df, i-1, self.sl_atr)
                    tp = close1 + self._atr_buf(df, i-1, self.tp_atr)
                elif close2 > df['vwap_upper2'].iloc[i-2] and close1 < vwap_upper2 and not np.isnan(ema200) and close1 < ema200:
                    signal = -1
                    sl = close1 + self._atr_buf(df, i-1, self.sl_atr)
                    tp = close1 - self._atr_buf(df, i-1, self.tp_atr)

            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        df['signal'] = signals
        df['sl'] = sl_prices
        df['tp'] = tp_prices
        
        return df
