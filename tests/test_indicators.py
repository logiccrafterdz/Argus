import unittest
import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backtest'))
from indicators import EMA, SMA, ATR, ADX, RSI, BollingerBands, SuperTrend, DonchianChannels, VWAP

class TestIndicators(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = pd.DataFrame({
            'open': np.random.uniform(1.09, 1.11, 100),
            'high': np.random.uniform(1.09, 1.11, 100),
            'low': np.random.uniform(1.09, 1.11, 100),
            'close': np.random.uniform(1.09, 1.11, 100),
            'tick_volume': np.random.randint(100, 1000, 100),
        })
        cls.df.index = pd.date_range('2024-01-01', periods=100, freq='h')

    def test_ema_length(self):
        result = EMA(self.df['close'], 14)
        self.assertEqual(len(result), 100)

    def test_bollinger_bands(self):
        upper, mid, lower = BollingerBands(self.df['close'], 20, 2)
        self.assertEqual(len(upper), 100)
        valid = ~(upper.isna() | mid.isna() | lower.isna())
        self.assertTrue((upper[valid] >= mid[valid]).all())
        self.assertTrue((mid[valid] >= lower[valid]).all())

    def test_donchian(self):
        upper, mid, lower = DonchianChannels(self.df, 20)
        self.assertEqual(len(upper), 100)
        valid = ~(upper.isna() | mid.isna() | lower.isna())
        self.assertTrue((upper[valid] >= mid[valid]).all())
        self.assertTrue((mid[valid] >= lower[valid]).all())

    def test_supertrend(self):
        st, direction = SuperTrend(self.df, 10, 3)
        self.assertEqual(len(st), 100)
        self.assertEqual(len(direction), 100)

    def test_donchian(self):
        upper, mid, lower = DonchianChannels(self.df, 20)
        self.assertEqual(len(upper), 100)
        valid = ~(upper.isna() | mid.isna() | lower.isna())
        self.assertTrue((upper[valid] >= mid[valid]).all())
        self.assertTrue((mid[valid] >= lower[valid]).all())

    def test_vwap(self):
        # VWAP needs a date column for groupby
        df = self.df.copy()
        df.set_index(pd.to_datetime(df.index), inplace=True)
        result = VWAP(df)
        self.assertTrue('date' in df.columns or 'date' in df.index.names)
        self.assertEqual(len(result), 100)

    def test_adx_marketregime_shape_consistency(self):
        from indicators import MarketRegime
        regime = MarketRegime(self.df)
        self.assertEqual(len(regime), len(self.df))

if __name__ == '__main__':
    unittest.main()
