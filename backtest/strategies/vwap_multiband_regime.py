from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from indicators import VWAP

class VWAPMultiBandRegime(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="VWAP_MultiBand_Regime",
            category="Institutional",
            regime_mask=1 | 2, # TREND | RANGE
            session_mask=7
        )
        
    def prepare_data(self, df):
        df['vwap'] = VWAP(df)
        
        # Calculate standard deviation for bands
        # A simple rolling std for illustration since exact VWAP stdev requires volume-weighted variance
        df['vwap_std'] = df['close'].rolling(20).std()
        df['vwap_upper1'] = df['vwap'] + df['vwap_std']
        df['vwap_lower1'] = df['vwap'] - df['vwap_std']
        df['vwap_upper2'] = df['vwap'] + 2 * df['vwap_std']
        df['vwap_lower2'] = df['vwap'] - 2 * df['vwap_std']
        
        signals = []
        sl_prices = []
        tp_prices = []
        
        for i in range(len(df)):
            signal = 0
            sl = np.nan
            tp = np.nan
            
            if i > 20:
                close1 = df['close'].iloc[i-1]
                close2 = df['close'].iloc[i-2]
                vwap_lower2 = df['vwap_lower2'].iloc[i-1]
                vwap_upper2 = df['vwap_upper2'].iloc[i-1]
                vwap = df['vwap'].iloc[i-1]
                
                # Reversal from 2nd VWAP band
                if close2 < df['vwap_lower2'].iloc[i-2] and close1 > vwap_lower2:
                    signal = 1
                    sl = df['low'].iloc[i-2] - 0.00050
                    tp = vwap
                elif close2 > df['vwap_upper2'].iloc[i-2] and close1 < vwap_upper2:
                    signal = -1
                    sl = df['high'].iloc[i-2] + 0.00050
                    tp = vwap

            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        df['signal'] = signals
        df['sl'] = sl_prices
        df['tp'] = tp_prices
        
        return df
