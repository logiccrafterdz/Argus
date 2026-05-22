import unittest
import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backtest'))
from market_structure import precompute_swings, is_bullish_structure, is_bearish_structure, get_liquidity_pools

class TestMarketStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        np.random.seed(42)
        cls.df = pd.DataFrame({
            'high': np.random.uniform(1.09, 1.11, 50),
            'low': np.random.uniform(1.09, 1.11, 50),
            'close': np.random.uniform(1.09, 1.11, 50),
        })

    def test_precompute_swings(self):
        highs, lows = precompute_swings(self.df)
        self.assertEqual(len(highs), 50)
        self.assertEqual(len(lows), 50)
        self.assertTrue(highs.dtype == bool)
        self.assertTrue(lows.dtype == bool)

    def test_is_bullish_structure(self):
        highs, lows = precompute_swings(self.df)
        for i in range(5, 50):
            result = is_bullish_structure(self.df, i, lookback=10, swing_lows=lows)
            self.assertIn(result, [True, False])

    def test_is_bearish_structure(self):
        highs, lows = precompute_swings(self.df)
        for i in range(5, 50):
            result = is_bearish_structure(self.df, i, lookback=10, swing_highs=highs)
            self.assertIn(result, [True, False])

    def test_get_liquidity_pools(self):
        highs, lows = precompute_swings(self.df)
        for i in range(10, 50):
            liq_high, liq_low = get_liquidity_pools(self.df, i, lookback=10, radius=2, threshold_points=0.00050, swing_highs=highs, swing_lows=lows)
            self.assertTrue(np.isnan(liq_high) or isinstance(liq_high, float))
            self.assertTrue(np.isnan(liq_low) or isinstance(liq_low, float))

    def test_market_regime_bitmask(self):
        from indicators import MarketRegime
        df = pd.DataFrame({
            'open': np.random.uniform(1.09, 1.11, 100),
            'high': np.random.uniform(1.09, 1.11, 100),
            'low': np.random.uniform(1.09, 1.11, 100),
            'close': np.random.uniform(1.09, 1.11, 100),
            'tick_volume': np.random.randint(100, 1000, 100),
        })
        df.index = pd.date_range('2024-01-01', periods=100, freq='h')
        regime = MarketRegime(df)
        self.assertEqual(len(regime), 100)
        # Valid bitmask values: 1(Trend), 2(Range), 4(Expansion), 8(Compression), 16(Reversal)
        valid = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 16, 17, 20, 24]
        for v in regime:
            self.assertIn(v, valid)

if __name__ == '__main__':
    unittest.main()
