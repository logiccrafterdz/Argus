from .base_strategy import BaseStrategy
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from indicators import SMA

class SMACrossover(BaseStrategy):
    def __init__(self, fast=20, slow=50):
        super().__init__(
            name="SMA_Crossover",
            category="Trend",
            regime_mask=1 | 2 | 4,  # TREND / RANGE / EXPANSION
            session_mask=7
        )
        self.fast = fast
        self.slow = slow
        self.disable_breakeven = False

    def prepare_data(self, df):
        df['sma_fast'] = SMA(df['close'], self.fast)
        df['sma_slow'] = SMA(df['close'], self.slow)
        self._add_atr_col(df)

        signals = []
        sl_prices = []
        tp_prices = []

        warmup = max(self.fast, self.slow) + 5
        for i in range(warmup, len(df)):
            signal = 0
            sl = np.nan
            tp = np.nan

            fast_now = df['sma_fast'].iloc[i]
            fast_prev = df['sma_fast'].iloc[i - 1]
            slow_now = df['sma_slow'].iloc[i]
            slow_prev = df['sma_slow'].iloc[i - 1]

            close_now = df['close'].iloc[i]
            atr1 = self._atr_buf(df, i - 1, 1.0)

            # Bullish crossover
            if fast_prev < slow_prev and fast_now >= slow_now and close_now > fast_now:
                signal = 1
                sl = close_now - atr1 * 2.0
                tp = close_now + atr1 * 4.0

            # Bearish crossover
            elif fast_prev > slow_prev and fast_now <= slow_now and close_now < fast_now:
                signal = -1
                sl = close_now + atr1 * 2.0
                tp = close_now - atr1 * 4.0

            signals.append(signal)
            sl_prices.append(sl)
            tp_prices.append(tp)

        pad = [0] * warmup
        pad_nan = [np.nan] * warmup

        df['signal'] = pad + signals
        df['sl'] = pad_nan + sl_prices
        df['tp'] = pad_nan + tp_prices

        return df
